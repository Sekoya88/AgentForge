"""LangGraph per-node step builders (ASR/TTS/LLM/tools/subagent/memory)."""

from __future__ import annotations

import base64
import json
import time
import uuid
from typing import TYPE_CHECKING, Any
from uuid import UUID

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langfuse import observe
from langgraph.types import interrupt

from app.config import Settings
from app.domain.attached_skill_binding import AttachedSkillBinding
from app.domain.execution_policy import ExecutionPolicyValidated
from app.domain.ports.agent_orchestrator import KnowledgeSearchFn, SubagentResolver
from app.domain.ports.execution_events import ExecutionEventEmitter
from app.domain.ports.sandbox_runtime import SandboxRuntime
from app.domain.value_objects import MessageDict
from app.infrastructure.orchestration.context_manager import apply_context_policy
from app.infrastructure.orchestration.graph_compile import definition_has_interrupt
from app.infrastructure.orchestration.graph_state import (
    GraphState as _State,
)
from app.infrastructure.orchestration.graph_state import (
    message_tail_preview as _message_tail_preview,
)
from app.infrastructure.orchestration.llm_invoke import invoke_chat_llm

if TYPE_CHECKING:
    from app.domain.entities.agent import Agent


def _langfuse_update_current_span(**kwargs: Any) -> None:
    """Update active Langfuse span; no-op if client unavailable or tracing disabled."""
    try:
        from langfuse import get_client

        get_client().update_current_span(**kwargs)
    except Exception:
        pass


_MAX_SUBAGENT_DEPTH = 5


def _build_asr_provider(
    cfg: dict[str, Any], settings: Settings, openai_key: str | None = None
) -> Any:
    provider = cfg.get("provider", "openai_whisper")
    if provider == "openai_whisper":
        from app.infrastructure.speech.providers.openai_whisper import OpenAIWhisperASR

        return OpenAIWhisperASR(api_key=openai_key or settings.openai_api_key)
    if provider == "finetuned_whisper":
        from app.infrastructure.speech.providers.http_finetuned_asr import HttpFinetunedASR

        url = cfg.get("endpoint_url")
        if not url or not str(url).strip():
            raise ValueError("finetuned_whisper requires graph node config.endpoint_url")
        hdrs = cfg.get("headers")
        headers = hdrs if isinstance(hdrs, dict) else None
        return HttpFinetunedASR(endpoint_url=str(url), headers=headers)
    raise ValueError(f"Unknown ASR provider: {provider!r}")


def _build_tts_provider(
    cfg: dict[str, Any], settings: Settings, openai_key: str | None = None
) -> Any:
    provider = cfg.get("provider", "openai_tts")
    if provider in ("openai_tts", "openai"):
        from app.infrastructure.speech.providers.openai_tts import OpenAITTS

        return OpenAITTS(api_key=openai_key or settings.openai_api_key)
    if provider == "elevenlabs":
        from app.infrastructure.speech.providers.elevenlabs_tts import ElevenLabsTTS

        return ElevenLabsTTS(api_key=settings.elevenlabs_api_key)
    if provider == "finetuned_tts":
        from app.infrastructure.speech.providers.http_finetuned_tts import HttpFinetunedTTS

        url = cfg.get("endpoint_url")
        if not url or not str(url).strip():
            raise ValueError("finetuned_tts requires graph node config.endpoint_url")
        hdrs = cfg.get("headers")
        headers = hdrs if isinstance(hdrs, dict) else None
        voice_id = cfg.get("voice_id")
        return HttpFinetunedTTS(
            endpoint_url=str(url),
            voice_id=str(voice_id) if voice_id else None,
            headers=headers,
        )
    raise ValueError(f"Unknown TTS provider: {provider!r}")


async def _run_asr_node(
    state: _State,
    cfg: dict[str, Any],
    settings: Settings,
    *,
    openai_key: str | None = None,
) -> dict[str, Any]:
    audio_b64 = state.get("audio_b64") or ""
    if not str(audio_b64).strip():
        return {
            "messages": [HumanMessage(content="[asr] No audio provided in state.")],
            "audio_b64": None,
        }
    try:
        audio_bytes = base64.b64decode(audio_b64)
    except Exception:
        return {
            "messages": [HumanMessage(content="[asr] Invalid base64 audio.")],
            "audio_b64": None,
        }
    provider = _build_asr_provider(cfg, settings, openai_key)
    language = cfg.get("language") or None
    filename = str(cfg.get("filename") or "audio.webm")
    transcript = await provider.transcribe(audio_bytes, language=language, filename=filename)
    return {"messages": [HumanMessage(content=transcript)], "audio_b64": None}


async def _run_tts_node(
    state: _State,
    cfg: dict[str, Any],
    settings: Settings,
    *,
    openai_key: str | None = None,
) -> dict[str, Any]:
    last_ai = next(
        (m for m in reversed(state.get("messages", [])) if isinstance(m, AIMessage)),
        None,
    )
    text = str(last_ai.content) if last_ai else ""
    provider = _build_tts_provider(cfg, settings, openai_key)
    voice = str(cfg.get("voice", "nova"))
    mp3_bytes = await provider.synthesize(text, voice=voice)
    return {"audio_b64": base64.b64encode(mp3_bytes).decode()}


def _merge_node_model_config(
    agent_model_config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(agent_model_config)
    if node_config.get("model") is not None:
        merged["model"] = node_config["model"]
    if node_config.get("temperature") is not None:
        merged["temperature"] = node_config["temperature"]
    return merged


async def _run_attached_skill_code(
    sandbox: SandboxRuntime,
    source_code: str,
    input_text: str,
    *,
    timeout_sec: float,
) -> str:
    """Execute skill `run(str) -> str` in an isolated subprocess (see SandboxRuntime)."""
    src_b64 = base64.b64encode(source_code.encode()).decode("ascii")
    inp_b64 = base64.b64encode(input_text.encode()).decode("ascii")
    _mode = "exe" + "c"
    driver = (
        "import base64,sys,builtins\n"
        f'_SRC_B64="{src_b64}"\n'
        f'_INP_B64="{inp_b64}"\n'
        "src=base64.b64decode(_SRC_B64).decode()\n"
        "ns={}\n"
        f"getattr(builtins, '{_mode}')(compile(src, '<skill>', '{_mode}'), ns, ns)\n"
        "run=ns.get('run')\n"
        "if run is None:\n"
        "    sys.stderr.write('Skill has no run()\\n')\n"
        "    sys.exit(2)\n"
        'inp=base64.b64decode(_INP_B64).decode(errors="replace")\n'
        "out=run(inp)\n"
        "sys.stdout.write(str(out))\n"
    )
    exit_code, out, err = await sandbox.run_python(driver, timeout_sec)
    if exit_code != 0:
        tail = (err or out or "").strip()
        return f"[skill_error code={exit_code}] {tail}"
    return out


@observe(as_type="tool", name="tool_dispatch")
async def _observed_tool_dispatch(
    tool_name: str,
    arg: str,
    handler,
) -> str:
    """Run tool handler with Langfuse span. `handler` is an async callable(arg) -> str."""
    _langfuse_update_current_span(
        name=f"tool:{tool_name}",
        input={"tool_name": tool_name, "arg": arg[:500]},
    )
    result = await handler(arg)
    _langfuse_update_current_span(output=str(result)[:500])
    return result


@observe(as_type="retriever", name="knowledge_retrieve")
async def _observed_retrieve_dispatch(arg: str, handler) -> str:
    _langfuse_update_current_span(
        input={"arg": arg[:500]},
    )
    result = await handler(arg)
    _langfuse_update_current_span(output=str(result)[:500])
    return result


async def _run_google_workspace_tool(
    tool_name: str,
    arg: str,
    access_token: str,
    scopes: frozenset[str],
) -> str:
    from app.infrastructure.auth.google_oauth_flow import (
        SCOPE_CALENDAR_EVENTS,
        SCOPE_CALENDAR_READONLY,
        SCOPE_GMAIL_READONLY,
        SCOPE_GMAIL_SEND,
    )
    from app.infrastructure.integrations.google_api_service import (
        GoogleApiService,
        emails_to_json,
        events_to_json,
    )

    svc = GoogleApiService(access_token)
    try:
        if tool_name == "read_gmail":
            if SCOPE_GMAIL_READONLY not in scopes:
                return json.dumps(
                    {"error": "Missing gmail.readonly scope; reconnect Google from Settings."}
                )
            max_results = 10
            query = "in:inbox"
            s = arg.strip()
            if s.startswith("{"):
                try:
                    j = json.loads(s)
                    max_results = int(j.get("max_results", 10))
                    query = str(j.get("q", "in:inbox"))
                except Exception:
                    query = s or "in:inbox"
            elif s:
                query = s
            emails = await svc.list_emails(max_results=max_results, query=query)
            return emails_to_json(emails)
        if tool_name == "send_gmail":
            if SCOPE_GMAIL_SEND not in scopes:
                return json.dumps(
                    {"error": "Missing gmail.send scope; reconnect Google from Settings."}
                )
            try:
                j = json.loads(arg.strip() or "{}")
            except json.JSONDecodeError:
                return json.dumps({"error": "send_gmail expects JSON: to, subject, body"})
            to = str(j.get("to", ""))
            subject = str(j.get("subject", ""))
            body = str(j.get("body", ""))
            if not to or not subject:
                return json.dumps({"error": "to and subject are required"})
            mid = await svc.send_email(to, subject, body)
            return json.dumps({"message_id": mid, "status": "sent"})
        if tool_name == "read_calendar":
            if SCOPE_CALENDAR_READONLY not in scopes:
                return json.dumps(
                    {"error": "Missing calendar.readonly scope; reconnect Google from Settings."}
                )
            days = 7
            s = arg.strip()
            if s.isdigit():
                days = int(s)
            elif s.startswith("{"):
                try:
                    days = int(json.loads(s).get("days_ahead", 7))
                except Exception:
                    pass
            events = await svc.list_events(days_ahead=days)
            return events_to_json(events)
        if tool_name == "create_calendar_event":
            if SCOPE_CALENDAR_EVENTS not in scopes:
                return json.dumps(
                    {"error": "Missing calendar.events scope; reconnect Google from Settings."}
                )
            try:
                j = json.loads(arg.strip() or "{}")
            except json.JSONDecodeError:
                return json.dumps(
                    {"error": "create_calendar_event expects JSON: title, start, end, ..."}
                )
            title = str(j.get("title", ""))
            start = str(j.get("start", ""))
            end = str(j.get("end", ""))
            if not title or not start or not end:
                return json.dumps({"error": "title, start, end ISO datetimes required"})
            loc = j.get("location")
            att = j.get("attendees")
            attendees = [str(a) for a in att] if isinstance(att, list) else None
            eid = await svc.create_event(
                title,
                start,
                end,
                location=str(loc) if loc else None,
                attendees=attendees,
            )
            return json.dumps({"event_id": eid})
        if tool_name == "delete_calendar_event":
            if SCOPE_CALENDAR_EVENTS not in scopes:
                return json.dumps(
                    {"error": "Missing calendar.events scope; reconnect Google from Settings."}
                )
            try:
                j = json.loads(arg.strip() or "{}")
            except json.JSONDecodeError:
                return json.dumps({"error": "delete_calendar_event expects JSON: event_id"})
            event_id = str(j.get("event_id", "")).strip()
            if not event_id:
                return json.dumps({"error": "event_id required"})
            await svc.delete_event(event_id)
            return json.dumps({"status": "deleted", "event_id": event_id})
    except Exception as e:
        return json.dumps({"error": str(e)})
    return json.dumps({"error": f"unknown tool {tool_name}"})


def _build_google_workspace_langchain_tools(
    access_token: str,
    scopes: frozenset[str],
) -> list[Any]:
    """LangChain tools for Gemini bind_tools; runs _run_google_workspace_tool."""
    from langchain_core.tools import tool

    from app.infrastructure.auth.google_oauth_flow import (
        SCOPE_CALENDAR_EVENTS,
        SCOPE_CALENDAR_READONLY,
        SCOPE_GMAIL_READONLY,
        SCOPE_GMAIL_SEND,
    )

    tools: list[Any] = []

    if SCOPE_GMAIL_READONLY in scopes:

        @tool
        async def read_gmail(query: str = "in:inbox", max_results: int = 10) -> str:
            """Read recent Gmail messages. query uses Gmail search syntax; max_results 1-50."""
            return await _run_google_workspace_tool(
                "read_gmail",
                json.dumps({"q": query, "max_results": max_results}),
                access_token,
                scopes,
            )

        tools.append(read_gmail)

    if SCOPE_GMAIL_SEND in scopes:

        @tool
        async def send_gmail(to: str, subject: str, body: str) -> str:
            """Send an email via the user's Gmail account."""
            return await _run_google_workspace_tool(
                "send_gmail",
                json.dumps({"to": to, "subject": subject, "body": body}),
                access_token,
                scopes,
            )

        tools.append(send_gmail)

    if SCOPE_CALENDAR_READONLY in scopes:

        @tool
        async def read_calendar(days_ahead: int = 7) -> str:
            """List upcoming events on the user's primary Google Calendar."""
            return await _run_google_workspace_tool(
                "read_calendar",
                json.dumps({"days_ahead": days_ahead}),
                access_token,
                scopes,
            )

        tools.append(read_calendar)

    if SCOPE_CALENDAR_EVENTS in scopes:

        @tool
        async def create_calendar_event(
            title: str,
            start: str,
            end: str,
            location: str = "",
            attendees_csv: str = "",
        ) -> str:
            """Create a calendar event. start/end are ISO 8601. Optional comma-separated emails."""
            payload: dict[str, Any] = {"title": title, "start": start, "end": end}
            if location.strip():
                payload["location"] = location.strip()
            if attendees_csv.strip():
                payload["attendees"] = [a.strip() for a in attendees_csv.split(",") if a.strip()]
            return await _run_google_workspace_tool(
                "create_calendar_event",
                json.dumps(payload),
                access_token,
                scopes,
            )

        tools.append(create_calendar_event)

        @tool
        async def delete_calendar_event(event_id: str) -> str:
            """Delete a calendar event by its event_id. Use read_calendar first to get the id."""
            return await _run_google_workspace_tool(
                "delete_calendar_event",
                json.dumps({"event_id": event_id}),
                access_token,
                scopes,
            )

        tools.append(delete_calendar_event)

    return tools


async def _invoke_google_llm_with_workspace_tools(
    prior_messages: list[BaseMessage],
    *,
    system_prompt: str,
    model_config: dict[str, Any],
    google_api_key: str,
    access_token: str,
    scopes: frozenset[str],
    settings: Settings,
    bus: ExecutionEventEmitter,
    cost_meter: Any = None,
    max_tool_rounds: int = 10,
) -> tuple[str, dict[str, Any]]:
    from langchain_google_genai import ChatGoogleGenerativeAI

    from app.infrastructure.orchestration.llm_invoke import (
        _get_observability_callbacks,
        _resolve_google_generative_model_name,
    )

    tools = _build_google_workspace_langchain_tools(access_token, scopes)
    if not tools:
        return await invoke_chat_llm(
            prior_messages,
            system_prompt=system_prompt,
            model_config=model_config,
            openai_api_key=None,
            google_api_key=google_api_key,
            anthropic_api_key=None,
        )

    temperature = model_config.get("temperature")
    if temperature is None:
        temperature = 0.2
    else:
        temperature = float(temperature)

    model_name = _resolve_google_generative_model_name(
        str(model_config.get("model") or "gemini-2.5-flash")
    )
    llm = ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=google_api_key,
        temperature=temperature,
    )
    bound = llm.bind_tools(tools)
    callbacks = _get_observability_callbacks(settings)

    lc_messages: list[BaseMessage] = []
    if system_prompt.strip():
        lc_messages.append(SystemMessage(content=system_prompt.strip()))
    lc_messages.extend(prior_messages)

    total_usage: dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0}
    model_label = str(model_config.get("model") or model_name)

    last_out: AIMessage | None = None
    for _ in range(max_tool_rounds):
        last_out = await bound.ainvoke(lc_messages, config={"callbacks": callbacks})
        usage = getattr(last_out, "usage_metadata", None)
        if isinstance(usage, dict):
            pt = int(usage.get("input_tokens", usage.get("prompt_tokens", 0)) or 0)
            ct = int(usage.get("output_tokens", usage.get("completion_tokens", 0)) or 0)
            total_usage["prompt_tokens"] += pt
            total_usage["completion_tokens"] += ct
            if cost_meter:
                cost_meter.add_usage(model_label, {"prompt_tokens": pt, "completion_tokens": ct})
                cost_meter.check_budget()

        tcalls = getattr(last_out, "tool_calls", None) or []
        if not tcalls:
            return str(last_out.content or "").strip() or "(empty)", total_usage

        lc_messages.append(last_out)
        for tc in tcalls:
            if isinstance(tc, dict):
                name = str(tc.get("name") or "")
                tid = tc.get("id") or str(uuid.uuid4())
                raw_args = tc.get("args")
            else:
                name = str(getattr(tc, "name", "") or "")
                tid = getattr(tc, "id", None) or str(uuid.uuid4())
                raw_args = getattr(tc, "args", None)

            if not name:
                continue

            if raw_args is None:
                arg_str = ""
            elif isinstance(raw_args, str):
                arg_str = raw_args
            elif isinstance(raw_args, dict):
                arg_str = json.dumps(raw_args)
            else:
                arg_str = str(raw_args)

            await bus.emit("tool_call", {"tool_name": name, "args": {"input": arg_str[:2000]}})
            try:
                result = await _run_google_workspace_tool(
                    name,
                    arg_str,
                    access_token,
                    scopes,
                )
            except Exception as e:
                result = json.dumps({"error": str(e)})
            preview = str(result)[:800]
            await bus.emit(
                "tool_result",
                {"tool_name": name, "result": f"Tool '{name}' result: {preview}"},
            )
            lc_messages.append(ToolMessage(content=str(result), tool_call_id=str(tid)))

    if last_out and (getattr(last_out, "tool_calls", None) or []):
        msg = (
            "J'ai atteint la limite d'actions pour ce tour. "
            "Reformule ou demande une étape à la fois."
        )
        return (msg, total_usage)
    return str(last_out.content if last_out else "") or "", total_usage


def _memory_store_for_step(state: dict[str, Any], config: RunnableConfig | None) -> Any:
    """Resolve memory store from state or runtime config (avoids msgpack checkpoint on store)."""
    m = state.get("__memory_store__")
    if m is not None:
        return m
    if config is not None:
        return (config.get("configurable") or {}).get("__memory_store__")
    return None


def build_step(
    node_id: str,
    spec: dict[str, Any],
    bus: ExecutionEventEmitter,
    agent_model_config: dict[str, Any],
    settings: Settings,
    attached_skills: dict[str, AttachedSkillBinding],
    sandbox: SandboxRuntime,
    skill_timeout_sec: float,
    knowledge_search: KnowledgeSearchFn | None,
    openai_key: str | None,
    google_key: str | None,
    subagent_resolver: SubagentResolver | None = None,
    subagent_depth: int = 0,
    anthropic_key: str | None = None,
    google_oauth_access_token: str | None = None,
    google_oauth_scopes: frozenset[str] | None = None,
    execution_policy: ExecutionPolicyValidated | None = None,
    cost_meter: Any = None,
):
    ntype = spec.get("type", "llm")

    async def step(state: _State, config: RunnableConfig | None = None):
        t0 = time.perf_counter()
        await bus.emit(
            "agent_start",
            {
                "agent_name": node_id,
                "node_type": ntype,
                "input_preview": _message_tail_preview(state["messages"]),
            },
        )
        if ntype == "interrupt":
            cfg = spec.get("config") or {}
            payload = {
                "node_id": node_id,
                "allowed_decisions": cfg.get("allowed_decisions", ["approve", "reject"]),
            }
            await bus.emit("interrupt", payload)
            answer = interrupt(payload)
            msg = AIMessage(content=f"[human_decision:{answer}]")
            dur = int((time.perf_counter() - t0) * 1000)
            await bus.emit(
                "agent_end",
                {
                    "agent_name": node_id,
                    "duration_ms": dur,
                    "output_preview": str(msg.content)[:500],
                },
            )
            return {"messages": [msg]}
        if ntype == "conditional":
            dur = int((time.perf_counter() - t0) * 1000)
            await bus.emit(
                "agent_end",
                {
                    "agent_name": node_id,
                    "duration_ms": dur,
                    "output_preview": "(router)",
                },
            )
            return {}
        if ntype == "tool":
            cfg = spec.get("config") or {}
            tool_name = cfg.get("tool_name", "tool")

            last_msg = next(
                (
                    m
                    for m in reversed(state["messages"])
                    if isinstance(m, (HumanMessage, AIMessage))
                ),
                None,
            )
            arg = str(last_msg.content) if last_msg else ""

            if execution_policy is not None:
                ok_tool, reason_tool = execution_policy.is_tool_allowed(tool_name)
                if not ok_tool:
                    msg = AIMessage(content=f"Tool '{tool_name}' blocked: {reason_tool}")
                    dur = int((time.perf_counter() - t0) * 1000)
                    await bus.emit(
                        "agent_end",
                        {
                            "agent_name": node_id,
                            "duration_ms": dur,
                            "output_preview": str(msg.content)[:500],
                        },
                    )
                    return {"messages": [msg]}

            if execution_policy is not None:
                ok_inp, reason_inp = execution_policy.is_input_allowed(tool_name, arg)
                if not ok_inp:
                    msg = AIMessage(content=f"Tool '{tool_name}' blocked: {reason_inp}")
                    dur = int((time.perf_counter() - t0) * 1000)
                    await bus.emit(
                        "agent_end",
                        {
                            "agent_name": node_id,
                            "duration_ms": dur,
                            "output_preview": str(msg.content)[:500],
                        },
                    )
                    return {"messages": [msg]}

            await bus.emit("tool_call", {"tool_name": tool_name, "args": {"input": arg}})

            skill_binding = attached_skills.get(tool_name)
            # Built-ins first, then registry skills (tool_name must match skill.name).
            if tool_name == "fetch":
                import urllib.request

                async def _fetch_handler(input_arg: str) -> str:
                    try:
                        req = urllib.request.Request(
                            input_arg, headers={"User-Agent": "AgentForge/1.0"}
                        )
                        with urllib.request.urlopen(req, timeout=5) as response:
                            return response.read().decode("utf-8")[:500]
                    except Exception as e:
                        return f"Fetch Error: {e}"

                handler = _fetch_handler

            elif tool_name == "echo":

                async def _echo_handler(input_arg: str) -> str:
                    return f"Echo: {input_arg}"

                handler = _echo_handler

            elif tool_name == "retrieve":
                top_k = int(cfg.get("top_k") or 5)

                async def _retrieve_handler(input_arg: str) -> str:
                    if knowledge_search is not None:
                        await bus.emit("rag_search", {"phase": "bm25", "query": input_arg[:200]})
                        await bus.emit(
                            "rag_search", {"phase": "semantic", "query": input_arg[:200]}
                        )
                        res = await knowledge_search(input_arg, top_k)
                        await bus.emit("rag_search", {"phase": "fusion_rrf"})
                        return res
                    return "[retrieve] Knowledge search is not available for this execution."

                handler = _retrieve_handler

            elif (
                google_oauth_access_token
                and google_oauth_scopes is not None
                and tool_name
                in (
                    "read_gmail",
                    "send_gmail",
                    "read_calendar",
                    "create_calendar_event",
                )
            ):

                async def _google_ws_handler(input_arg: str) -> str:
                    return await _run_google_workspace_tool(
                        tool_name,
                        input_arg,
                        google_oauth_access_token,
                        google_oauth_scopes,
                    )

                handler = _google_ws_handler

            elif skill_binding is not None:
                if skill_binding.skill_type == "instruction":

                    async def _instruction_handler(input_arg: str) -> str:  # noqa: F811
                        return skill_binding.instructions or "(no instructions)"

                    handler = _instruction_handler
                else:
                    if not skill_binding.security_validated:
                        await bus.emit(
                            "skill_notice",
                            {
                                "tool_name": tool_name,
                                "message": "Skill is not marked security_validated",
                            },
                        )

                    async def _skill_handler(input_arg: str) -> str:  # noqa: F811
                        res = await _run_attached_skill_code(
                            sandbox,
                            skill_binding.source_code,
                            input_arg,
                            timeout_sec=skill_timeout_sec,
                        )
                        await bus.emit(
                            "skill_summary",
                            {"skill_name": tool_name, "result_preview": str(res)[:200]},
                        )
                        return res

                    handler = _skill_handler
            else:

                async def _stub_handler(input_arg: str) -> str:  # noqa: F811
                    return f"[tool:{tool_name}] executed with input '{input_arg}' (stub)."

                handler = _stub_handler

            if (
                execution_policy is not None
                and tool_name in execution_policy.require_human_approval_for
            ):
                payload = {
                    "node_id": node_id,
                    "tool_name": tool_name,
                    "tool_input": arg[:200],
                    "allowed_decisions": ["approve", "reject"],
                }
                await bus.emit("interrupt", payload)
                decision = interrupt(payload)
                if str(decision).lower() == "reject":
                    msg = AIMessage(content=f"Tool '{tool_name}' execution rejected by human.")
                    dur = int((time.perf_counter() - t0) * 1000)
                    await bus.emit(
                        "agent_end",
                        {
                            "agent_name": node_id,
                            "duration_ms": dur,
                            "output_preview": str(msg.content)[:500],
                        },
                    )
                    return {"messages": [msg]}

            if tool_name == "retrieve":
                res = await _observed_retrieve_dispatch(arg=arg, handler=handler)
            else:
                res = await _observed_tool_dispatch(tool_name=tool_name, arg=arg, handler=handler)

            msg = AIMessage(
                content=f"Tool '{tool_name}' result: {res}",
                additional_kwargs={"_tool_result": True},
            )
            await bus.emit("tool_result", {"tool_name": tool_name, "result": msg.content})
            dur = int((time.perf_counter() - t0) * 1000)
            await bus.emit(
                "agent_end",
                {
                    "agent_name": node_id,
                    "duration_ms": dur,
                    "output_preview": str(msg.content)[:500],
                },
            )
            return {"messages": [msg]}
        if ntype == "subagent":
            cfg = spec.get("config") or {}
            subagent_id_str = cfg.get("subagent_id")
            label = cfg.get("subagent_name") or node_id

            if subagent_depth >= _MAX_SUBAGENT_DEPTH:
                msg = AIMessage(
                    content=(
                        f"[subagent:{label}] Error: maximum subagent recursion depth"
                        f" ({_MAX_SUBAGENT_DEPTH}) exceeded."
                    )
                )
                dur = int((time.perf_counter() - t0) * 1000)
                await bus.emit(
                    "agent_end",
                    {
                        "agent_name": node_id,
                        "duration_ms": dur,
                        "output_preview": str(msg.content)[:500],
                    },
                )
                return {"messages": [msg]}

            if not subagent_id_str or subagent_resolver is None:
                msg = AIMessage(
                    content=(
                        f"[subagent:{label}] Error: subagent_id not configured"
                        " or resolver unavailable."
                    )
                )
                dur = int((time.perf_counter() - t0) * 1000)
                await bus.emit(
                    "agent_end",
                    {
                        "agent_name": node_id,
                        "duration_ms": dur,
                        "output_preview": str(msg.content)[:500],
                    },
                )
                return {"messages": [msg]}

            try:
                target_agent: Agent = await subagent_resolver(UUID(subagent_id_str))
            except Exception as e:
                msg = AIMessage(content=f"[subagent:{label}] Error resolving agent: {e}")
                dur = int((time.perf_counter() - t0) * 1000)
                await bus.emit(
                    "agent_end",
                    {
                        "agent_name": node_id,
                        "duration_ms": dur,
                        "output_preview": str(msg.content)[:500],
                    },
                )
                return {"messages": [msg]}

            # Check if subagent graph contains interrupt nodes — not supported in nested execution
            subagent_def = (
                target_agent.graph_definition.to_dict() if target_agent.graph_definition else {}
            )
            if definition_has_interrupt(subagent_def):
                msg = AIMessage(
                    content=(
                        f"[subagent:{label}] Error: subagent graphs with interrupt nodes"
                        " are not supported in nested execution."
                    )
                )
                dur = int((time.perf_counter() - t0) * 1000)
                await bus.emit(
                    "agent_end",
                    {
                        "agent_name": node_id,
                        "duration_ms": dur,
                        "output_preview": str(msg.content)[:500],
                    },
                )
                return {"messages": [msg]}

            # Delegate to sub-orchestrator (lazy import avoids import cycle with this module)
            from app.infrastructure.orchestration.langgraph_orchestrator import (
                LangGraphAgentOrchestrator,
            )

            sub_orchestrator = LangGraphAgentOrchestrator(
                settings=settings,
                sandbox=sandbox,
                skill_timeout_sec=skill_timeout_sec,
            )
            from app.domain.message_content import coerce_message_content_to_str

            input_msgs = [
                MessageDict(
                    role="user" if isinstance(m, HumanMessage) else "assistant",
                    content=coerce_message_content_to_str(m.content),
                )
                for m in state["messages"]
                if isinstance(m, (HumanMessage, AIMessage))
            ]
            try:
                sub_result = await sub_orchestrator.run(
                    agent_id=target_agent.id,
                    graph_definition=target_agent.graph_definition,
                    model_config=target_agent.model_config,
                    input_messages=input_msgs,
                    emitter=bus,
                    agent_label=target_agent.name,
                    openai_key=openai_key,
                    google_key=google_key,
                    anthropic_key=anthropic_key,
                    subagent_resolver=subagent_resolver,
                    subagent_depth=subagent_depth + 1,
                    google_oauth_access_token=google_oauth_access_token,
                    google_oauth_scopes=google_oauth_scopes,
                )
                last_out = (
                    sub_result.output_messages[-1].content
                    if sub_result.output_messages
                    else "(no output)"
                )
                msg = AIMessage(content=f"[subagent:{label}] {last_out}")
            except Exception as e:
                msg = AIMessage(content=f"[subagent:{label}] Execution error: {e}")

            dur = int((time.perf_counter() - t0) * 1000)
            await bus.emit(
                "agent_end",
                {
                    "agent_name": node_id,
                    "duration_ms": dur,
                    "output_preview": str(msg.content)[:500],
                },
            )
            return {"messages": [msg]}

        if ntype == "asr":
            cfg = spec.get("config") or {}
            try:
                result = await _run_asr_node(state, cfg, settings, openai_key=openai_key)
            except Exception as e:
                result = {
                    "messages": [HumanMessage(content=f"[asr] Error: {e}")],
                    "audio_b64": None,
                }
            dur = int((time.perf_counter() - t0) * 1000)
            last_m = result.get("messages", [{}])[-1] if result.get("messages") else None
            preview = str(getattr(last_m, "content", last_m))[:200] if last_m else ""
            await bus.emit(
                "agent_end",
                {
                    "agent_name": node_id,
                    "duration_ms": dur,
                    "output_preview": preview,
                },
            )
            return result

        if ntype == "tts":
            cfg = spec.get("config") or {}
            try:
                result = await _run_tts_node(state, cfg, settings, openai_key=openai_key)
            except Exception as e:
                msg = AIMessage(content=f"[tts] Error: {e}")
                dur = int((time.perf_counter() - t0) * 1000)
                await bus.emit(
                    "agent_end",
                    {
                        "agent_name": node_id,
                        "duration_ms": dur,
                        "output_preview": str(msg.content)[:500],
                    },
                )
                return {"messages": [msg]}
            dur = int((time.perf_counter() - t0) * 1000)
            await bus.emit(
                "agent_end",
                {
                    "agent_name": node_id,
                    "duration_ms": dur,
                    "output_preview": f"[audio:{len(result.get('audio_b64', ''))} chars b64]",
                },
            )
            return result

        if ntype in ("memory_save", "memory_recall"):
            cfg = spec.get("config") or {}
            key = openai_key or settings.openai_api_key
            memory_store = _memory_store_for_step(state, config)
            user_id_mem = state.get("__user_id__")
            agent_id_mem = state.get("__agent_id__")

            if not key or memory_store is None or user_id_mem is None or agent_id_mem is None:
                msg = AIMessage(content=f"[{ntype}] Memory unavailable (missing key or store).")
                dur = int((time.perf_counter() - t0) * 1000)
                await bus.emit(
                    "agent_end",
                    {"agent_name": node_id, "duration_ms": dur, "output_preview": str(msg.content)},
                )
                return {"messages": [msg]}

            last_human = next(
                (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), None
            )
            text_for_embed = str(last_human.content) if last_human else ""

            try:
                import httpx as _httpx

                async with _httpx.AsyncClient() as _hc:
                    _r = await _hc.post(
                        "https://api.openai.com/v1/embeddings",
                        headers={"Authorization": f"Bearer {key}"},
                        json={"model": "text-embedding-3-small", "input": text_for_embed},
                        timeout=30.0,
                    )
                    _r.raise_for_status()
                    embedding = _r.json()["data"][0]["embedding"]
            except Exception as e:
                msg = AIMessage(content=f"[{ntype}] Embedding error: {e}")
                dur = int((time.perf_counter() - t0) * 1000)
                await bus.emit(
                    "agent_end",
                    {"agent_name": node_id, "duration_ms": dur, "output_preview": str(msg.content)},
                )
                return {"messages": [msg]}

            if ntype == "memory_save":
                importance = float(cfg.get("importance", 0.5))
                try:
                    await memory_store.save(
                        user_id=user_id_mem,
                        agent_id=agent_id_mem,
                        content=text_for_embed,
                        embedding=embedding,
                        importance=importance,
                    )
                    msg = AIMessage(content=f"[memory_save] Saved: {text_for_embed[:120]}")
                except Exception as e:
                    msg = AIMessage(content=f"[memory_save] Error: {e}")
            else:
                top_k = int(cfg.get("top_k", 5))
                try:
                    memories = await memory_store.recall(
                        user_id=user_id_mem,
                        agent_id=agent_id_mem,
                        query_embedding=embedding,
                        top_k=top_k,
                    )
                    if memories:
                        recall_text = "\n".join(f"- {m.content}" for m in memories)
                        msg = HumanMessage(content=f"[memory_recall]\n{recall_text}")
                    else:
                        msg = HumanMessage(content="[memory_recall] No relevant memories found.")
                except Exception as e:
                    msg = AIMessage(content=f"[memory_recall] Error: {e}")

            dur = int((time.perf_counter() - t0) * 1000)
            await bus.emit(
                "agent_end",
                {
                    "agent_name": node_id,
                    "duration_ms": dur,
                    "output_preview": str(msg.content)[:500],
                },
            )
            return {"messages": [msg]}

        cfg = spec.get("config") or {}
        prompt = str(cfg.get("prompt") or "")
        # Inject instruction-type skills into the LLM system prompt
        instruction_parts: list[str] = []
        for sk in attached_skills.values():
            if sk.skill_type == "instruction" and sk.instructions:
                instruction_parts.append(f"## Skill: {sk.name}\n{sk.instructions}")
        if instruction_parts:
            skills_block = "\n\n---\n\n".join(instruction_parts)
            prompt = (
                f"{prompt}\n\n# Attached Skills\n\n{skills_block}"
                if prompt
                else f"# Attached Skills\n\n{skills_block}"
            )
        node_mc = _merge_node_model_config(agent_model_config, cfg)

        current_tokens = cost_meter.total_prompt_tokens if cost_meter else 0
        state_messages = await apply_context_policy(
            state["messages"], execution_policy, invoke_chat_llm, node_mc, settings, current_tokens
        )

        provider_lc = str(node_mc.get("provider") or "").lower()
        gkey_llm = google_key or settings.google_api_key
        ws_tools_enabled = cfg.get("google_workspace_tools", True) is not False
        google_tool_list = (
            _build_google_workspace_langchain_tools(
                google_oauth_access_token,
                google_oauth_scopes,
            )
            if (
                ws_tools_enabled
                and google_oauth_access_token
                and google_oauth_scopes is not None
                and provider_lc in ("google", "gemini")
                and gkey_llm
            )
            else []
        )

        try:
            await bus.emit(
                "llm_start",
                {"node_id": node_id, "provider": provider_lc, "model": node_mc.get("model")},
            )
            if google_tool_list:
                text, usage = await _invoke_google_llm_with_workspace_tools(
                    state_messages,
                    system_prompt=prompt,
                    model_config=node_mc,
                    google_api_key=gkey_llm,
                    access_token=google_oauth_access_token,
                    scopes=google_oauth_scopes,
                    settings=settings,
                    bus=bus,
                    cost_meter=cost_meter,
                )
            else:
                text, usage = await invoke_chat_llm(
                    state_messages,
                    system_prompt=prompt,
                    model_config=node_mc,
                    openai_api_key=openai_key or settings.openai_api_key,
                    google_api_key=google_key or settings.google_api_key,
                    anthropic_api_key=anthropic_key or settings.anthropic_api_key,
                )
                if cost_meter:
                    model_name = node_mc.get("model", "")
                    cost_meter.add_usage(model_name, usage)
                    cost_meter.check_budget()
            await bus.emit("llm_end", {"node_id": node_id, "tokens": usage})
        except Exception as e:
            dur = int((time.perf_counter() - t0) * 1000)
            await bus.emit(
                "agent_end",
                {
                    "agent_name": node_id,
                    "duration_ms": dur,
                    "output_preview": f"(error) {e!s}"[:500],
                },
            )
            raise
        msg = AIMessage(content=text)
        dur = int((time.perf_counter() - t0) * 1000)
        await bus.emit(
            "agent_end",
            {
                "agent_name": node_id,
                "duration_ms": dur,
                "output_preview": str(msg.content)[:500],
            },
        )
        return {"messages": [msg]}

    return step
