import json
import re
import builtins
from typing import Any, Annotated, TypedDict
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]

class LocalAgent:
    def __init__(self, data: dict[str, Any]):
        self.data = data
        self.name = data.get("name", "Local Agent")
        self.graph_definition = data.get("graph_definition", {"nodes": [], "edges": []})
        self.model_config = data.get("model_config", {})
        self.skills = data.get("skills", [])
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

    def _create_step_function(self, node_id: str, node_type: str, config: dict, skill_map: dict):
        async def step(state: AgentState):
            messages = state["messages"]
            if node_type == "llm":
                from langchain_openai import ChatOpenAI
                from langchain_google_genai import ChatGoogleGenerativeAI

                provider = self.model_config.get("provider", "openai")
                model_name = self.model_config.get("model", "gpt-4o")
                temperature = self.model_config.get("temperature", 0.7)
                sys_prompt = config.get("system_prompt", "")

                lc_messages = []
                if sys_prompt:
                    lc_messages.append(SystemMessage(content=sys_prompt))
                lc_messages.extend(messages)

                if provider == "openai":
                    llm = ChatOpenAI(model=model_name, temperature=temperature)
                elif provider in ("google", "gemini"):
                    llm = ChatGoogleGenerativeAI(model=model_name, temperature=temperature)
                else:
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
                return {"messages": [AIMessage(content=f"[subagent:{node_id}] Local subagent execution is not supported yet.")]}

            elif node_type == "interrupt":
                return {"messages": [AIMessage(content=f"[interrupt:{node_id}] Interrupts are bypassed locally.")]}

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
        return await self._compiled_graph.ainvoke(input_dict)

    def invoke(self, input_dict: dict[str, Any]):
        return self._compiled_graph.invoke(input_dict)


def load_agent(path_or_dict: str | dict) -> LocalAgent:
    """Load an AgentForge exported JSON file and return a runner."""
    if isinstance(path_or_dict, str):
        with open(path_or_dict, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = path_or_dict

    return LocalAgent(data)
