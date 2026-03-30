import hashlib
import json
import re
import builtins
from typing import Any, Annotated, TypedDict, Callable, Dict
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

# Plugin system for custom nodes
_NODE_REGISTRY: Dict[str, Callable] = {}

def node(node_type: str):
    """Decorator to register a custom node type."""
    def decorator(func: Callable):
        _NODE_REGISTRY[node_type] = func
        return func
    return decorator

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    audio_b64: str | None

class LocalAgent:
    def __init__(self, data: dict[str, Any], subagent_resolver: Callable[[str, Any], Any] = None, interrupt_resolver: Callable[[str, Any], Any] = None):
        self.data = data
        self.name = data.get("name", "Local Agent")
        self.graph_definition = data.get("graph_definition", {"nodes": [], "edges": []})
        self.model_config = data.get("model_config", {})
        self.skills = data.get("skills", [])
        self.subagent_resolver = subagent_resolver
        self.interrupt_resolver = interrupt_resolver

        # Verify SHA256 of each embedded skill's source_code
        for skill in self.skills:
            if isinstance(skill, dict) and "sha256" in skill and "source_code" in skill:
                source_code = skill["source_code"]
                expected = skill["sha256"]
                if source_code and hashlib.sha256(source_code.encode()).hexdigest() != expected:
                    print(
                        f"warning: skill '{skill.get('name', skill.get('id', '?'))}' "
                        f"SHA256 mismatch — source_code may have been tampered with"
                    )

        self._compiled_graph = self._compile()

    def _compile(self):
        nodes = self.graph_definition.get("nodes", [])
        edges = self.graph_definition.get("edges", [])

        # If no nodes, default
        if not nodes:
            nodes = [{"id": "llm", "type": "llm", "config": {}}]
            edges = [{"from": "START", "to": "llm"}, {"from": "llm", "to": "END"}]

        builder = StateGraph(AgentState)

        # Build skills map
        skill_map = {
            s["id"]: s for s in self.skills if "id" in s
        }
        # Also map by name if possible
        for s in self.skills:
            if "name" in s:
                skill_map[s["name"]] = s

        # Build node step functions
        for node in nodes:
            node_id = node.get("id")
            node_type = node.get("type", "llm")
            config = node.get("config", {})

            # Create a localized step function
            step_func = self._create_step_function(node_id, node_type, config, skill_map)
            builder.add_node(node_id, step_func)

        # Add edges
        # We need to find outgoing edges for each node
        outgoing_edges = {}
        for e in edges:
            from_ = e.get("from")
            if from_ not in outgoing_edges:
                outgoing_edges[from_] = []
            outgoing_edges[from_].append(e)

        for node in nodes:
            node_id = node.get("id")
            outs = outgoing_edges.get(node_id, [])
            if not outs:
                builder.add_edge(node_id, END)
                continue

            if len(outs) == 1 and not outs[0].get("condition"):
                to = outs[0].get("to")
                builder.add_edge(node_id, END if to == "END" else to)
            else:
                # Conditional edges
                builder.add_conditional_edges(
                    node_id,
                    self._create_condition_func(outs),
                    { e.get("to"): (END if e.get("to") == "END" else e.get("to")) for e in outs }
                )

        # START edges
        start_edges = outgoing_edges.get("START", [])
        for e in start_edges:
            to = e.get("to")
            builder.add_edge(START, END if to == "END" else to)

        return builder.compile()

    @staticmethod
    def _coerce_state_input(input_dict: dict[str, Any]) -> dict[str, Any]:
        out = dict(input_dict)
        if "messages" not in out:
            out["messages"] = []
        out.setdefault("audio_b64", None)
        return out

    def _create_step_function(self, node_id: str, node_type: str, config: dict, skill_map: dict):
        async def step(state: AgentState):
            messages = state["messages"]
            if node_type == "llm":
                from agentforge.llm_factory import build_llm

                provider = self.model_config.get("provider", "openai")
                model_name = self.model_config.get("model", "gpt-4o")
                temperature = float(self.model_config.get("temperature", 0.7))
                base_url = self.model_config.get("base_url")
                options = self.model_config.get("options") or {}
                sys_prompt = config.get("system_prompt", "")

                lc_messages = []
                if sys_prompt:
                    lc_messages.append(SystemMessage(content=sys_prompt))
                lc_messages.extend(messages)

                try:
                    llm = build_llm(
                        provider=provider,
                        model=model_name,
                        temperature=temperature,
                        base_url=base_url,
                        options=options,
                    )
                except ValueError:
                    from langchain_openai import ChatOpenAI
                    llm = ChatOpenAI(model="gpt-4o", temperature=temperature)

                res = await llm.ainvoke(lc_messages)
                return {"messages": [res]}

            elif node_type == "tool":
                tool_name = config.get("tool_name", "unknown")
                # find the last AI message
                last_ai = ""
                for m in reversed(messages):
                    if isinstance(m, AIMessage):
                        last_ai = str(m.content)
                        break

                skill = skill_map.get(tool_name)
                if not skill:
                    # just a stub
                    res = f"[tool:{tool_name}] not found in exported skills."
                else:
                    if skill.get("skill_type") == "instruction":
                        res = skill.get("instructions", "(no instructions)")
                    else:
                        code = skill.get("source_code", "")
                        # Run locally
                        try:
                            local_env = {}
                            getattr(builtins, "exec")(code, local_env)
                            if "run" in local_env:
                                res = local_env["run"](last_ai)
                            else:
                                res = "Error: no run() function found in skill code."
                        except Exception as e:
                            res = f"Error executing tool locally: {str(e)}"

                return {"messages": [AIMessage(content=f"Tool '{tool_name}' result: {res}")]}

            elif node_type == "subagent":
                agent_id = config.get("agent_id")
                if self.subagent_resolver:
                    res = await self.subagent_resolver(agent_id, messages)
                    if isinstance(res, str):
                        res = AIMessage(content=res)
                    elif isinstance(res, dict) and "messages" in res:
                        return res
                    return {"messages": [res]}
                return {"messages": [AIMessage(content=f"[subagent:{node_id}] Local subagent execution bypassed (no resolver configured).")]}

            elif node_type == "interrupt":
                if self.interrupt_resolver:
                    res = await self.interrupt_resolver(node_id, state)
                    if isinstance(res, str):
                        res = AIMessage(content=res)
                    elif isinstance(res, dict) and "messages" in res:
                        return res
                    return {"messages": [res]}
                return {"messages": [AIMessage(content=f"[interrupt:{node_id}] Interrupts are bypassed locally.")]}

            elif node_type == "asr":
                import base64

                audio_b64 = state.get("audio_b64") or ""
                if not str(audio_b64).strip():
                    return {
                        "messages": [AIMessage(content="[asr] No audio_b64 in state.")],
                        "audio_b64": None,
                    }
                try:
                    audio_bytes = base64.b64decode(audio_b64)
                except Exception:
                    return {
                        "messages": [AIMessage(content="[asr] Invalid base64 audio.")],
                        "audio_b64": None,
                    }
                provider_name = config.get("provider", "openai_whisper")
                language = config.get("language") or None
                filename = str(config.get("filename") or "audio.webm")
                if provider_name == "openai_whisper":
                    try:
                        from agentforge.speech.openai_whisper import LocalWhisperASR

                        provider = LocalWhisperASR()
                        transcript = await provider.transcribe(
                            audio_bytes, language=language, filename=filename
                        )
                    except ImportError:
                        transcript = "[asr] openai package not installed (pip install openai)"
                    except Exception as e:
                        transcript = f"[asr] Error: {e}"
                else:
                    transcript = f"[asr] provider '{provider_name}' not supported locally."
                return {"messages": [HumanMessage(content=transcript)], "audio_b64": None}

            elif node_type == "tts":
                import base64

                last_ai = next(
                    (m for m in reversed(messages) if isinstance(m, AIMessage)),
                    None,
                )
                text = str(last_ai.content) if last_ai else ""
                provider_name = config.get("provider", "openai_tts")
                voice = config.get("voice", "nova")
                if provider_name in ("openai_tts", "openai"):
                    try:
                        from agentforge.speech.openai_tts import LocalOpenAITTS

                        provider = LocalOpenAITTS()
                        mp3_bytes = await provider.synthesize(text, voice=voice)
                        return {"audio_b64": base64.b64encode(mp3_bytes).decode()}
                    except ImportError:
                        return {
                            "messages": [
                                AIMessage(content="[tts] openai package not installed (pip install openai)")
                            ]
                        }
                    except Exception as e:
                        return {"messages": [AIMessage(content=f"[tts] Error: {e}")]}
                return {
                    "messages": [
                        AIMessage(
                            content=f"[tts] provider '{provider_name}' not supported locally."
                        )
                    ]
                }

            elif node_type in _NODE_REGISTRY:
                plugin_func = _NODE_REGISTRY[node_type]
                try:
                    res = await plugin_func(state, config)
                    if isinstance(res, str):
                        res = AIMessage(content=res)
                    elif isinstance(res, dict) and "messages" in res:
                        return res
                    return {"messages": [res]}
                except Exception as e:
                    return {"messages": [AIMessage(content=f"Error in custom node '{node_type}': {str(e)}")]}

            else:
                return {"messages": [AIMessage(content=f"Unknown node type: {node_type}")]}

        return step

    def _create_condition_func(self, outs: list[dict]):
        def pick_next(state: AgentState) -> str:
            last_ai = ""
            for m in reversed(state["messages"]):
                if isinstance(m, AIMessage):
                    last_ai = str(m.content)
                    break

            default_dest = None
            for e in outs:
                cond = e.get("condition")
                cond_type = e.get("condition_type", "contains")
                dest = END if e["to"] == "END" else e["to"]

                if cond_type == "always" or cond in (None, "", "always"):
                    default_dest = dest
                    continue

                if not last_ai or not cond:
                    continue

                matched = False
                if cond_type == "contains":
                    matched = str(cond).lower() in last_ai.lower()
                elif cond_type == "regex":
                    try:
                        matched = bool(re.search(str(cond), last_ai, re.IGNORECASE))
                    except re.error:
                        matched = False
                elif cond_type == "json_path":
                    try:
                        import json
                        json_start = last_ai.find("{")
                        json_end = last_ai.rfind("}") + 1
                        if json_start >= 0 and json_end > json_start:
                            data = json.loads(last_ai[json_start:json_end])
                            if "==" in str(cond):
                                path, expected = str(cond).split("==", 1)
                                keys = path.strip().split(".")
                                val = data
                                for k in keys:
                                    val = val[k]
                                matched = str(val) == expected.strip()
                            else:
                                keys = str(cond).strip().split(".")
                                val = data
                                for k in keys:
                                    val = val[k]
                                matched = bool(val)
                    except Exception:
                        matched = False

                if matched:
                    return dest
            return default_dest if default_dest is not None else END
        return pick_next

    async def ainvoke(self, input_dict: dict[str, Any]):
        return await self._compiled_graph.ainvoke(self._coerce_state_input(input_dict))

    def invoke(self, input_dict: dict[str, Any]):
        return self._compiled_graph.invoke(self._coerce_state_input(input_dict))

    async def astream(self, input_dict: dict[str, Any]):
        coerced = self._coerce_state_input(input_dict)
        async for event in self._compiled_graph.astream(coerced, stream_mode="updates"):
            yield event

    async def astream_events(self, input_dict: dict[str, Any], version="v2"):
        coerced = self._coerce_state_input(input_dict)
        async for event in self._compiled_graph.astream_events(coerced, version=version):
            yield event

def load_agent(path_or_dict: str | dict, subagent_resolver=None, interrupt_resolver=None) -> LocalAgent:
    """Load an AgentForge exported JSON file and return a runner."""
    if isinstance(path_or_dict, str):
        with open(path_or_dict, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = path_or_dict

    return LocalAgent(data, subagent_resolver=subagent_resolver, interrupt_resolver=interrupt_resolver)
