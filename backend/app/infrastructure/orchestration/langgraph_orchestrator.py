import base64
import json
import re
import time
import uuid
from collections import defaultdict
from collections.abc import Awaitable, Callable, Sequence
from typing import TYPE_CHECKING, Any
from uuid import UUID

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langfuse import observe
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from app.config import Settings, get_settings
from app.domain.attached_skill_binding import AttachedSkillBinding
from app.domain.execution_policy import ExecutionPolicyValidated, parse_execution_policy
from app.domain.graph_definition import GraphDefinitionValidated
from app.domain.orchestration_result import OrchestrationResult
from app.domain.ports.agent_orchestrator import (
    AgentOrchestrator,
    KnowledgeSearchFn,
    SubagentResolver,
)
from app.domain.ports.execution_events import ExecutionEventEmitter, NullExecutionEmitter
from app.domain.ports.sandbox_runtime import SandboxRuntime
from app.domain.value_objects import AgentModelConfig, MessageDict
from app.infrastructure.orchestration.checkpoint_registry import get_checkpointer
from app.infrastructure.orchestration.context_manager import apply_context_policy
from app.infrastructure.orchestration.cost_meter import ExecutionCostMeter
from app.infrastructure.orchestration.graph_state import (
    GraphState as _State,
)
from app.infrastructure.orchestration.graph_state import (
    dicts_to_messages as _dicts_to_messages,
)
from app.infrastructure.orchestration.graph_state import (
    last_ai_text as _last_ai_text,
)
from app.infrastructure.orchestration.graph_state import (
    lg_node_name as _lg_node_name,
)
from app.infrastructure.orchestration.graph_state import (
    message_tail_preview as _message_tail_preview,
)
from app.infrastructure.orchestration.graph_state import (
    messages_to_dicts as _messages_to_dicts,
)
from app.infrastructure.orchestration.llm_invoke import (
    _get_observability_callbacks,
    invoke_chat_llm,
)
from app.infrastructure.sandbox.subprocess_sandbox import SubprocessSandboxRuntime

if TYPE_CHECKING:
    from app.domain.entities.agent import Agent


def _langfuse_update_current_span(**kwargs: Any) -> None:
    """Update active Langfuse span; no-op if client unavailable or tracing disabled."""
    try:
        from langfuse import get_client

        get_client().update_current_span(**kwargs)
    except Exception:
        pass


def _langfuse_enrich_agent_trace(
    *,
    user_id: UUID | None = None,
    session_id: str | None = None,
    execution_id: UUID | None = None,
) -> None:
    """Attach user/session/execution to the current trace for Langfuse filtering."""
    meta: dict[str, Any] = {}
    if user_id is not None:
        meta["user_id"] = str(user_id)
    if session_id:
        meta["session_id"] = session_id
    if execution_id is not None:
        meta["execution_id"] = str(execution_id)
    if meta:
        _langfuse_update_current_span(metadata=meta)


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


def _definition_has_interrupt(definition: dict[str, Any]) -> bool:
    for n in definition.get("nodes") or []:
        if n.get("type") == "interrupt":
            return True
    return False


def _default_definition() -> dict[str, Any]:
    return {
        "graph_schema_version": "1.0",
        "nodes": [{"id": "default", "type": "llm", "config": {}}],
        "edges": [],
        "entry_point": "default",
    }


def _eval_single_condition(text: str, cond: str | None, cond_type: str) -> bool:
    """Evaluate a single (non-compound) edge condition against *text*.

    Handles: contains, not_contains, equals, regex, json_path, gt, lt.
    Does NOT handle 'and'/'or' to keep evaluation flat (no recursion).
    Returns False on any error rather than raising.
    """
    if not text or not cond:
        return False

    if cond_type == "contains":
        return str(cond).lower() in text.lower()

    if cond_type == "not_contains":
        return str(cond).lower() not in text.lower()

    if cond_type == "equals":
        return str(cond).strip().lower() == text.strip().lower()

    if cond_type == "regex":
        try:
            return bool(re.search(str(cond), text, re.IGNORECASE))
        except re.error:
            return False

    if cond_type == "json_path":
        try:
            json_start = text.find("{")
            json_end = text.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                data = json.loads(text[json_start:json_end])
                if "==" in str(cond):
                    path, expected = str(cond).split("==", 1)
                    keys = path.strip().split(".")
                    val = data
                    for k in keys:
                        val = val[k]
                    return str(val) == expected.strip()
                else:
                    keys = str(cond).strip().split(".")
                    val = data
                    for k in keys:
                        val = val[k]
                    return bool(val)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            return False
        return False

    if cond_type in ("gt", "lt"):
        nums = re.findall(r"-?\d+(?:\.\d+)?", text)
        if nums:
            try:
                val = float(nums[0])
                threshold = float(str(cond))
                return val > threshold if cond_type == "gt" else val < threshold
            except ValueError:
                return False
        return False

    # Unknown cond_type — fail safe
    return False


def _pick_next(
    state: _State,
    outs: list[dict[str, Any]],
) -> str:
    last_ai = _last_ai_text(state["messages"])
    default_dest: str | None = None

    for e in outs:
        cond = e.get("condition")
        cond_type = e.get("condition_type", "contains")
        dest = _lg_node_name(e["to"])

        # "always" or empty condition -> use as default fallback
        if cond_type == "always" or cond in (None, "", "always"):
            default_dest = dest
            continue

        if not last_ai or not cond:
            continue

        matched = False

        if cond_type in ("contains", "not_contains", "equals", "regex", "json_path", "gt", "lt"):
            matched = _eval_single_condition(last_ai, cond, cond_type)

        elif cond_type == "and":
            try:
                sub_conditions = json.loads(str(cond)) if isinstance(cond, str) else cond
                matched = all(
                    _eval_single_condition(
                        last_ai,
                        sc.get("condition"),
                        sc.get("condition_type", "contains"),
                    )
                    for sc in sub_conditions
                )
            except (json.JSONDecodeError, TypeError, AttributeError):
                matched = False

        elif cond_type == "or":
            try:
                sub_conditions = json.loads(str(cond)) if isinstance(cond, str) else cond
                matched = any(
                    _eval_single_condition(
                        last_ai,
                        sc.get("condition"),
                        sc.get("condition_type", "contains"),
                    )
                    for sc in sub_conditions
                )
            except (json.JSONDecodeError, TypeError, AttributeError):
                matched = False

        if matched:
            return dest

    return default_dest if default_dest is not None else END


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


def _attached_skills_by_name(
    bindings: Sequence[AttachedSkillBinding],
) -> dict[str, AttachedSkillBinding]:
    m: dict[str, AttachedSkillBinding] = {}
    for b in bindings:
        if b.name not in m:
            m[b.name] = b
    return m


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


def _build_step(
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

    async def step(state: _State):
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
            if _definition_has_interrupt(subagent_def):
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

            # Delegate to sub-orchestrator (new instance, same settings/sandbox)
            # LangGraphAgentOrchestrator is defined in this same module; no import needed
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
            memory_store = state.get("__memory_store__")
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


def _compile_state_graph(
    definition: dict[str, Any],
    bus: ExecutionEventEmitter,
    agent_model_config: dict[str, Any],
    settings: Settings,
    attached_skills: dict[str, AttachedSkillBinding],
    sandbox: SandboxRuntime,
    skill_timeout_sec: float,
    knowledge_search: KnowledgeSearchFn | None,
    openai_key: str | None = None,
    google_key: str | None = None,
    subagent_resolver: SubagentResolver | None = None,
    subagent_depth: int = 0,
    anthropic_key: str | None = None,
    google_oauth_access_token: str | None = None,
    google_oauth_scopes: frozenset[str] | None = None,
    execution_policy: ExecutionPolicyValidated | None = None,
    cost_meter: Any = None,
) -> StateGraph:
    nodes_map: dict[str, dict[str, Any]] = {
        n["id"]: n for n in (definition.get("nodes") or []) if "id" in n
    }
    raw_edges = definition.get("edges") or []
    by_from: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for e in raw_edges:
        if "from" in e and "to" in e:
            by_from[e["from"]].append(e)
    entry = definition.get("entry_point")
    if not entry or entry not in nodes_map:
        entry = next(iter(nodes_map))

    g = StateGraph(_State)
    for nid, spec in nodes_map.items():
        g.add_node(
            _lg_node_name(nid),
            _build_step(
                nid,
                spec,
                bus,
                agent_model_config,
                settings,
                attached_skills,
                sandbox,
                skill_timeout_sec,
                knowledge_search,
                openai_key,
                google_key,
                subagent_resolver,
                subagent_depth,
                anthropic_key,
                google_oauth_access_token,
                google_oauth_scopes,
                execution_policy,
                cost_meter,
            ),
        )

    g.add_edge(START, _lg_node_name(entry))

    for nid in nodes_map:
        outs = by_from.get(nid, [])
        src = _lg_node_name(nid)
        if not outs:
            g.add_edge(src, END)
            continue
        if len(outs) == 1 and outs[0].get("condition") in (None, "", "always"):
            g.add_edge(src, _lg_node_name(outs[0]["to"]))
            continue

        def make_router(edges_out: list[dict[str, Any]]):
            def route(state: _State) -> Any:
                return _pick_next(state, edges_out)

            return route

        dests = {_lg_node_name(e["to"]) for e in outs}
        dests.add(END)
        path_map: dict[Any, str] = {d: d for d in dests if d != END}
        path_map[END] = END
        g.add_conditional_edges(src, make_router(outs), path_map)

    return g


def _process_invoke_result(
    result: dict[str, Any],
    *,
    duration_ms: int,
    bus: ExecutionEventEmitter,
    agent_id: UUID,
    agent_label: str | None,
    execution_id: UUID | None,
    had_checkpoint: bool,
    cost_meter: ExecutionCostMeter | None = None,
) -> OrchestrationResult:
    intrs = result.get("__interrupt__") or []
    msgs = result.get("messages") or []
    out_dicts = _messages_to_dicts(msgs)
    token_usage = cost_meter.get_token_usage_dict() if cost_meter else None
    audio_out = result.get("audio_b64")
    out_b64 = audio_out if isinstance(audio_out, str) else None

    if intrs:
        first = intrs[0]
        val = getattr(first, "value", first)
        iid = getattr(first, "id", None)
        payload: dict[str, Any] = {"interrupt_id": str(iid) if iid else None}
        if isinstance(val, dict):
            payload.update(val)
        else:
            payload["value"] = val
        return OrchestrationResult(
            out_dicts, token_usage, duration_ms, payload, output_audio_b64=out_b64
        )
    return OrchestrationResult(out_dicts, token_usage, duration_ms, None, output_audio_b64=out_b64)


class LangGraphAgentOrchestrator(AgentOrchestrator):
    def __init__(
        self,
        settings: Settings | None = None,
        sandbox: SandboxRuntime | None = None,
        skill_timeout_sec: float = 15.0,
    ) -> None:
        self._settings = settings or get_settings()
        self._sandbox = sandbox or SubprocessSandboxRuntime()
        self._skill_timeout_sec = skill_timeout_sec

    @observe(as_type="agent", name="agent_run")
    async def run(
        self,
        agent_id: UUID,
        graph_definition: GraphDefinitionValidated,
        model_config: AgentModelConfig,
        input_messages: list[MessageDict],
        *,
        emitter: ExecutionEventEmitter | None = None,
        agent_label: str | None = None,
        execution_id: UUID | None = None,
        attached_skills: Sequence[AttachedSkillBinding] | None = None,
        knowledge_search: Callable[[str, int], Awaitable[str]] | None = None,
        openai_key: str | None = None,
        google_key: str | None = None,
        anthropic_key: str | None = None,
        subagent_resolver: SubagentResolver | None = None,
        subagent_depth: int = 0,
        google_oauth_access_token: str | None = None,
        google_oauth_scopes: frozenset[str] | None = None,
        execution_policy: dict[str, Any] | ExecutionPolicyValidated | None = None,
        graph_extra: dict[str, Any] | None = None,
        langfuse_user_id: UUID | None = None,
        langfuse_session_id: str | None = None,
    ) -> OrchestrationResult:
        lf_meta: dict[str, Any] = {"model_config": model_config.to_dict()}
        if langfuse_user_id is not None:
            lf_meta["user_id"] = str(langfuse_user_id)
        if langfuse_session_id:
            lf_meta["session_id"] = langfuse_session_id
        if execution_id is not None:
            lf_meta["execution_id"] = str(execution_id)
        _langfuse_update_current_span(
            input={"agent_id": str(agent_id), "agent_name": agent_label},
            metadata=lf_meta,
        )
        bus: ExecutionEventEmitter = emitter or NullExecutionEmitter()
        definition = graph_definition.to_dict() if graph_definition else {"nodes": [], "edges": []}
        if not definition.get("nodes"):
            definition = _default_definition()

        need_cp = _definition_has_interrupt(definition)
        if need_cp and execution_id is None:
            raise ValueError("execution_id is required when the graph contains interrupt nodes")

        parsed_policy: ExecutionPolicyValidated | None = None
        if isinstance(execution_policy, ExecutionPolicyValidated):
            parsed_policy = execution_policy
        elif isinstance(execution_policy, dict):
            parsed_policy = parse_execution_policy(execution_policy)

        max_cost_usd = parsed_policy.max_cost_usd if parsed_policy else None
        cost_meter = ExecutionCostMeter(max_cost_usd=max_cost_usd)

        skill_map = _attached_skills_by_name(attached_skills or ())
        g = _compile_state_graph(
            definition,
            bus,
            model_config.to_dict(),
            self._settings,
            skill_map,
            self._sandbox,
            self._skill_timeout_sec,
            knowledge_search,
            openai_key,
            google_key,
            subagent_resolver,
            subagent_depth,
            anthropic_key,
            google_oauth_access_token,
            google_oauth_scopes,
            parsed_policy,
            cost_meter,
        )
        t0 = time.perf_counter()

        callbacks = _get_observability_callbacks(self._settings)
        cfg: dict[str, Any] = {"callbacks": callbacks}

        initial_state: dict[str, Any] = {
            "messages": _dicts_to_messages(input_messages),
            "audio_b64": None,
        }
        if graph_extra and graph_extra.get("audio_b64") is not None:
            initial_state["audio_b64"] = graph_extra["audio_b64"]
        for inj in ("__memory_store__", "__user_id__", "__agent_id__"):
            if graph_extra and graph_extra.get(inj) is not None:
                initial_state[inj] = graph_extra[inj]

        if need_cp:
            async with get_checkpointer() as checkpointer:
                compiled = g.compile(checkpointer=checkpointer)
                cfg["configurable"] = {"thread_id": str(execution_id)}
                result = await compiled.ainvoke(initial_state, cfg)
        else:
            compiled = g.compile()
            result = await compiled.ainvoke(initial_state, cfg)

        duration_ms = int((time.perf_counter() - t0) * 1000)

        orch = _process_invoke_result(
            result,
            duration_ms=duration_ms,
            bus=bus,
            agent_id=agent_id,
            agent_label=agent_label,
            execution_id=execution_id,
            had_checkpoint=need_cp,
            cost_meter=cost_meter,
        )
        return orch

    @observe(as_type="agent", name="agent_resume")
    async def resume(
        self,
        execution_id: UUID,
        agent_id: UUID,
        graph_definition: GraphDefinitionValidated,
        model_config: AgentModelConfig,
        resume_value: Any,
        *,
        emitter: ExecutionEventEmitter | None = None,
        agent_label: str | None = None,
        attached_skills: Sequence[AttachedSkillBinding] | None = None,
        knowledge_search: Callable[[str, int], Awaitable[str]] | None = None,
        openai_key: str | None = None,
        google_key: str | None = None,
        anthropic_key: str | None = None,
        subagent_resolver: SubagentResolver | None = None,
        google_oauth_access_token: str | None = None,
        google_oauth_scopes: frozenset[str] | None = None,
        execution_policy: dict[str, Any] | ExecutionPolicyValidated | None = None,
        langfuse_user_id: UUID | None = None,
        langfuse_session_id: str | None = None,
    ) -> OrchestrationResult:
        _langfuse_enrich_agent_trace(
            user_id=langfuse_user_id,
            session_id=langfuse_session_id,
            execution_id=execution_id,
        )
        parsed_resume_policy: ExecutionPolicyValidated | None = None
        if isinstance(execution_policy, ExecutionPolicyValidated):
            parsed_resume_policy = execution_policy
        elif isinstance(execution_policy, dict):
            parsed_resume_policy = parse_execution_policy(execution_policy)

        max_cost_resume = parsed_resume_policy.max_cost_usd if parsed_resume_policy else None
        cost_meter = ExecutionCostMeter(max_cost_usd=max_cost_resume)

        bus: ExecutionEventEmitter = emitter or NullExecutionEmitter()
        definition = (
            graph_definition.to_dict()
            if graph_definition and graph_definition.nodes
            else _default_definition()
        )
        skill_map = _attached_skills_by_name(attached_skills or ())
        g = _compile_state_graph(
            definition,
            bus,
            model_config.to_dict(),
            self._settings,
            skill_map,
            self._sandbox,
            self._skill_timeout_sec,
            knowledge_search,
            openai_key,
            google_key,
            subagent_resolver,
            0,
            anthropic_key,
            google_oauth_access_token,
            google_oauth_scopes,
            parsed_resume_policy,
            cost_meter,
        )

        callbacks = _get_observability_callbacks(self._settings)
        cfg: dict[str, Any] = {
            "configurable": {"thread_id": str(execution_id)},
            "callbacks": callbacks,
        }

        async with get_checkpointer() as checkpointer:
            compiled = g.compile(checkpointer=checkpointer)
            snapshot = await checkpointer.aget_tuple(cfg)
            if snapshot is None:
                raise ValueError("No checkpoint for this execution; cannot resume")
            t0 = time.perf_counter()
            result = await compiled.ainvoke(Command(resume=resume_value), cfg)

        duration_ms = int((time.perf_counter() - t0) * 1000)
        orch = _process_invoke_result(
            result,
            duration_ms=duration_ms,
            bus=bus,
            agent_id=agent_id,
            agent_label=agent_label,
            execution_id=execution_id,
            had_checkpoint=True,
            cost_meter=cost_meter,
        )
        return orch
