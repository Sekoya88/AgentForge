"""Forge Assistant service — direct LLM chat with tool use and Redis SSE streaming."""

from __future__ import annotations

import asyncio
import json
import logging
from uuid import UUID, uuid4

import redis.asyncio as redis

from app.infrastructure.events.redis_execution_stream import (
    RedisStreamEmitter,
    execution_stream_key,
)
from app.infrastructure.persistence.postgres.forge_repos import (
    ForgeConversationRepo,
    ForgeExecutionRepo,
)
from app.infrastructure.persistence.postgres.models import ForgeConversationModel

log = logging.getLogger(__name__)

FORGE_SYSTEM_PROMPT = """You are the Forge Assistant, the intelligent companion built into AgentForge — an enterprise platform for building, testing, and deploying LLM agents.

## Your role
You help users with:
- Building and configuring agents in AgentForge (graph-based workflows with LangGraph)
- Understanding and using MCP (Model Context Protocol) servers
- Using the AgentForge SDK (Python: `agentforge-sdk`)
- Creating agent skills (Python code bundles with tools)
- Setting up knowledge bases (RAG with indexed sources)
- Running red-team campaigns (security testing with adversarial scenarios)
- Fine-tuning models with QLoRA on Modal serverless GPU
- Scheduling agents with cron expressions
- Google Workspace integration (Calendar, Gmail via OAuth)
- Debugging failed executions and interpreting execution logs
- A/B testing agents with the compare variants feature

## AgentForge Key Concepts

**Agents** — Defined by a graph (nodes + edges). Node types: LLM, Tool, Condition, Human-in-the-loop (interrupt). Each agent has a model_config (provider, model, temperature, system_prompt) and an execution_policy.

**Skills** — Python code bundles with LangChain tools. Attached to agents. Users upload .py files or install from the skills marketplace.

**Knowledge** — Indexed sources (URLs, files, text). Embedded with sentence-transformers, searched via cosine similarity. Injected as context in agent prompts.

**Campaigns** — Red-team test suites. Define adversarial test cases (jailbreaks, prompt injections) run against an agent. Produces security scorecard.

**MCP** — Agents can expose tools as MCP servers or consume external MCP servers. Configured in agent graph definition.

**SDK** — `pip install agentforge-sdk`. Use `AgentForgeClient(base_url=..., api_key=...)` to run agents programmatically: `client.run(agent_id=..., message=...)`.

**Fine-tuning** — QLoRA fine-tuning on Modal. Upload examples (instruction/response pairs), launch job, monitor training loss, deploy as inference endpoint.

**Executions** — Each agent run creates an Execution record. Accessible via dashboard or `GET /api/v1/agents/{id}/executions`.

## Your tools
- `web_search`: Search the web for current information
- `python_repl`: Execute Python code (data analysis, calculations, file parsing)
- `list_agents`: See the user's current agents

Always be direct, technical, and helpful. When the user asks how to do something in AgentForge, give concrete step-by-step instructions."""

# Tool definitions (Anthropic input_schema format — converted per-provider in helpers)
FORGE_TOOLS = [
    {
        "name": "web_search",
        "description": "Search the web for current information, documentation, or answers.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "python_repl",
        "description": (
            "Execute Python code in a sandboxed environment. "
            "Use for calculations, data analysis, generating charts (as text output), etc."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Python code to execute"},
            },
            "required": ["code"],
        },
    },
    {
        "name": "list_agents",
        "description": "List the current user's agents in AgentForge.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]


class ForgeService:
    def __init__(
        self,
        conv_repo: ForgeConversationRepo,
        exec_repo: ForgeExecutionRepo,
        redis_client: redis.Redis,
        db_factory,  # async_sessionmaker
        openai_key: str | None = None,
        google_key: str | None = None,
        anthropic_key: str | None = None,
        tavily_key: str | None = None,
        user_id: UUID | None = None,
    ):
        self._conv = conv_repo
        self._exec = exec_repo
        self._redis = redis_client
        self._db_factory = db_factory
        self._keys = {
            "openai": openai_key,
            "google": google_key,
            "anthropic": anthropic_key,
            "tavily": tavily_key,
        }
        self._user_id = user_id

    async def create_conversation(
        self,
        user_id: UUID,
        provider: str,
        model: str,
        title: str | None = None,
    ) -> ForgeConversationModel:
        return await self._conv.create(user_id, provider, model, title)

    async def list_conversations(self, user_id: UUID) -> list[ForgeConversationModel]:
        return await self._conv.list_by_user(user_id)

    async def delete_conversation(self, user_id: UUID, conv_id: UUID) -> None:
        await self._conv.delete(conv_id, user_id)

    async def get_messages(self, user_id: UUID, conv_id: UUID) -> list[dict]:
        """Return flat message history for a conversation (user+assistant turns only)."""
        conv = await self._conv.get(conv_id, user_id)
        if not conv:
            return []
        executions = await self._exec.list_by_conversation(conv_id, limit=50)
        messages: list[dict] = []
        for exe in executions:
            for msg in exe.input_messages or []:
                if msg.get("role") == "user" and isinstance(msg.get("content"), str):
                    messages.append({"role": "user", "content": msg["content"]})
            for msg in exe.output_messages or []:
                if msg.get("role") == "assistant" and isinstance(msg.get("content"), str):
                    messages.append({"role": "assistant", "content": msg["content"]})
        return messages

    async def execute(
        self,
        user_id: UUID,
        conv_id: UUID,
        message: str,
        *,
        provider: str | None = None,
        model: str | None = None,
    ) -> UUID:
        """Start a forge execution. Returns execution_id immediately; streams to Redis."""
        conv = await self._conv.get(conv_id, user_id)
        if not conv:
            raise ValueError(f"Conversation {conv_id} not found")

        eff_provider = provider or conv.provider
        eff_model = model or conv.model

        # Load prior messages from executions on this thread
        prior = await self._exec.list_by_conversation(conv_id, limit=20)
        history: list[dict] = []
        for p in prior:
            for msg in p.input_messages or []:
                if msg.get("role") == "user" and isinstance(msg.get("content"), str):
                    history.append({"role": "user", "content": msg["content"]})
            for msg in p.output_messages or []:
                if msg.get("role") == "assistant" and isinstance(msg.get("content"), str):
                    history.append({"role": "assistant", "content": msg["content"]})

        input_messages = [{"role": "user", "content": message}]

        exe = await self._exec.create(user_id, conv_id, conv.thread_id, input_messages)
        await self._conv.update_last_message(conv_id)

        stream_key = execution_stream_key(exe.id)
        emitter = RedisStreamEmitter(self._redis, stream_key)

        asyncio.create_task(
            _run_forge_loop(
                execution_id=exe.id,
                conv_id=conv_id,
                history=history,
                new_message=message,
                provider=eff_provider,
                model=eff_model,
                api_keys=self._keys,
                user_id=user_id,
                emitter=emitter,
                db_factory=self._db_factory,
            )
        )
        return exe.id


# ---------------------------------------------------------------------------
# Background loop — provider-dispatch
# ---------------------------------------------------------------------------


async def _run_forge_loop(
    execution_id: UUID,
    conv_id: UUID,
    history: list[dict],
    new_message: str,
    provider: str,
    model: str,
    api_keys: dict,
    user_id: UUID,
    emitter: RedisStreamEmitter,
    db_factory,
) -> None:
    """Background task: run the LLM tool-use loop and stream tokens to Redis."""
    # history is already filtered to plain-string user/assistant turns
    messages: list[dict] = [*history, {"role": "user", "content": new_message}]

    token_usage: dict = {"input_tokens": 0, "output_tokens": 0}
    final_text = ""

    try:
        if provider == "anthropic":
            final_text, token_usage = await _anthropic_loop(
                messages, model, api_keys.get("anthropic"), emitter, api_keys
            )
        elif provider in ("google", "gemini"):
            final_text, token_usage = await _gemini_loop(
                messages, model, api_keys.get("google"), emitter, api_keys
            )
        else:  # openai default
            final_text, token_usage = await _openai_loop(
                messages, model, api_keys.get("openai"), emitter, api_keys
            )

        output_msgs = [{"role": "assistant", "content": final_text}]
        async with db_factory() as session:
            from app.infrastructure.persistence.postgres.forge_repos import (
                ForgeExecutionRepo as _Repo,
            )

            repo = _Repo(session)
            await repo.complete(execution_id, output_msgs, token_usage)
            await session.commit()

        await emitter.emit("complete", {"status": "completed", "execution_id": str(execution_id)})

    except Exception as e:
        log.exception("Forge loop failed for execution %s", execution_id)
        async with db_factory() as session:
            from app.infrastructure.persistence.postgres.forge_repos import (
                ForgeExecutionRepo as _Repo,
            )

            repo = _Repo(session)
            await repo.fail(execution_id, str(e))
            await session.commit()
        await emitter.emit("error", {"status": "failed", "message": str(e)})


# ---------------------------------------------------------------------------
# Tool execution (shared)
# ---------------------------------------------------------------------------


async def _call_tool(name: str, inp: dict, api_keys: dict, emitter: RedisStreamEmitter) -> str:
    """Execute a single tool and return a string result."""
    from app.infrastructure.integrations.python_repl import python_repl
    from app.infrastructure.integrations.tavily_search import tavily_search

    await emitter.emit("tool_call", {"name": name, "input": inp})
    try:
        if name == "web_search":
            tavily_key = api_keys.get("tavily")
            if not tavily_key:
                result = {"error": "Tavily API key not configured. Add it in Settings."}
            else:
                result = await tavily_search(inp.get("query", ""), tavily_key)
        elif name == "python_repl":
            result = await python_repl(inp.get("code", ""))
        elif name == "list_agents":
            result = {
                "message": "Agent listing requires DB access — not yet available in tool context."
            }
        else:
            result = {"error": f"Unknown tool: {name}"}
    except Exception as exc:
        result = {"error": str(exc)}

    await emitter.emit("tool_result", {"name": name, "result": result})
    return json.dumps(result, default=str)


# ---------------------------------------------------------------------------
# Anthropic provider — native tool-use loop
# ---------------------------------------------------------------------------


async def _anthropic_loop(
    messages: list[dict],
    model: str,
    api_key: str | None,
    emitter: RedisStreamEmitter,
    api_keys: dict,
) -> tuple[str, dict]:
    """Anthropic streaming loop with tool use. Returns (final_text, token_usage)."""
    if not api_key:
        raise ValueError("Anthropic API key not configured")

    import anthropic

    client = anthropic.AsyncAnthropic(api_key=api_key)
    tools = [
        {"name": t["name"], "description": t["description"], "input_schema": t["input_schema"]}
        for t in FORGE_TOOLS
    ]

    msgs = list(messages)  # mutable copy
    total_input = 0
    total_output = 0
    final_text = ""

    for _iteration in range(8):
        accumulated_text = ""
        stop_reason = "end_turn"
        raw_content: list = []

        async with client.messages.stream(
            model=model,
            max_tokens=4096,
            system=FORGE_SYSTEM_PROMPT,
            messages=msgs,
            tools=tools,
        ) as stream:
            async for event in stream:
                ev_type = type(event).__name__
                if ev_type == "RawContentBlockDeltaEvent":
                    delta = event.delta
                    if hasattr(delta, "type") and delta.type == "text_delta":
                        accumulated_text += delta.text
                        await emitter.emit("token", {"text": delta.text})
            final_msg = await stream.get_final_message()
            total_input += final_msg.usage.input_tokens
            total_output += final_msg.usage.output_tokens
            stop_reason = final_msg.stop_reason or "end_turn"
            raw_content = [b.model_dump() for b in final_msg.content]

        final_text = accumulated_text

        if stop_reason != "tool_use":
            break

        # Extract tool calls
        tool_calls = [
            {"id": b["id"], "name": b["name"], "input": b["input"]}
            for b in raw_content
            if b.get("type") == "tool_use"
        ]
        if not tool_calls:
            break

        # Append assistant turn (Anthropic native: content is a list of blocks)
        msgs.append({"role": "assistant", "content": raw_content})

        # Execute tools and append tool_result blocks in a single user turn
        tool_result_blocks = []
        for tc in tool_calls:
            out = await _call_tool(tc["name"], tc.get("input", {}), api_keys, emitter)
            tool_result_blocks.append(
                {"type": "tool_result", "tool_use_id": tc["id"], "content": out}
            )
        msgs.append({"role": "user", "content": tool_result_blocks})

    return final_text, {"input_tokens": total_input, "output_tokens": total_output}


# ---------------------------------------------------------------------------
# OpenAI provider — native tool-use loop
# ---------------------------------------------------------------------------


async def _openai_loop(
    messages: list[dict],
    model: str,
    api_key: str | None,
    emitter: RedisStreamEmitter,
    api_keys: dict,
) -> tuple[str, dict]:
    """OpenAI streaming loop with tool use. Returns (final_text, token_usage)."""
    if not api_key:
        raise ValueError("OpenAI API key not configured")

    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=api_key)
    oai_tools = [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"],
            },
        }
        for t in FORGE_TOOLS
    ]

    # Build OpenAI messages: system + history (plain string content only)
    oai_msgs: list[dict] = [{"role": "system", "content": FORGE_SYSTEM_PROMPT}]
    for m in messages:
        oai_msgs.append({"role": m["role"], "content": m["content"]})

    total_input = 0
    total_output = 0
    final_text = ""

    for _iteration in range(8):
        accumulated_text = ""
        tool_calls_raw: dict[int, dict] = {}
        stop_reason = "stop"

        stream = await client.chat.completions.create(
            model=model,
            messages=oai_msgs,
            tools=oai_tools,
            stream=True,
            stream_options={"include_usage": True},
        )

        async for chunk in stream:
            choice = chunk.choices[0] if chunk.choices else None
            if choice:
                delta = choice.delta
                if delta.content:
                    accumulated_text += delta.content
                    await emitter.emit("token", {"text": delta.content})
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in tool_calls_raw:
                            tool_calls_raw[idx] = {"id": "", "name": "", "arguments": ""}
                        if tc.id:
                            tool_calls_raw[idx]["id"] = tc.id
                        if tc.function and tc.function.name:
                            tool_calls_raw[idx]["name"] = tc.function.name
                        if tc.function and tc.function.arguments:
                            tool_calls_raw[idx]["arguments"] += tc.function.arguments
                if choice.finish_reason:
                    stop_reason = choice.finish_reason
            if chunk.usage:
                total_input += chunk.usage.prompt_tokens or 0
                total_output += chunk.usage.completion_tokens or 0

        final_text = accumulated_text

        if stop_reason != "tool_calls" or not tool_calls_raw:
            break

        # Parse tool calls
        tool_calls: list[dict] = []
        for tc in tool_calls_raw.values():
            try:
                inp = json.loads(tc["arguments"]) if tc["arguments"] else {}
            except json.JSONDecodeError:
                inp = {}
            tool_calls.append({"id": tc["id"], "name": tc["name"], "input": inp})

        # Append assistant message with tool_calls in OpenAI format
        oai_msgs.append(
            {
                "role": "assistant",
                "content": accumulated_text or None,
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {"name": tc["name"], "arguments": json.dumps(tc["input"])},
                    }
                    for tc in tool_calls
                ],
            }
        )

        # Execute tools and append tool messages
        for tc in tool_calls:
            out = await _call_tool(tc["name"], tc.get("input", {}), api_keys, emitter)
            oai_msgs.append({"role": "tool", "tool_call_id": tc["id"], "content": out})

    return final_text, {"input_tokens": total_input, "output_tokens": total_output}


# ---------------------------------------------------------------------------
# Gemini provider — native tool-use loop (google.genai SDK)
# ---------------------------------------------------------------------------


async def _gemini_loop(
    messages: list[dict],
    model: str,
    api_key: str | None,
    emitter: RedisStreamEmitter,
    api_keys: dict,
) -> tuple[str, dict]:
    """Gemini streaming loop with tool use. Returns (final_text, token_usage)."""
    if not api_key:
        raise ValueError("Google API key not configured")

    import google.genai as genai
    from google.genai import types as gt

    client = genai.Client(api_key=api_key)

    gemini_tools = [
        gt.Tool(
            function_declarations=[
                gt.FunctionDeclaration(
                    name=t["name"],
                    description=t["description"],
                    parameters=t["input_schema"],
                )
                for t in FORGE_TOOLS
            ]
        )
    ]

    config = gt.GenerateContentConfig(
        system_instruction=FORGE_SYSTEM_PROMPT,
        tools=gemini_tools,
    )

    # Build Gemini contents (role: "user" or "model", parts: list of strings)
    contents: list[gt.Content] = []
    for m in messages:
        role = "user" if m["role"] == "user" else "model"
        content = m.get("content", "")
        if isinstance(content, str) and content:
            contents.append(gt.Content(role=role, parts=[gt.Part(text=content)]))

    final_text = ""

    for _iteration in range(8):
        accumulated_text = ""

        async for chunk in await client.aio.models.generate_content_stream(
            model=model,
            contents=contents,
            config=config,
        ):
            if chunk.text:
                accumulated_text += chunk.text
                await emitter.emit("token", {"text": chunk.text})

        final_text = accumulated_text

        # Check for function calls
        tool_calls: list[dict] = []
        try:
            for part in chunk.candidates[0].content.parts if chunk.candidates else []:  # type: ignore[union-attr]
                if hasattr(part, "function_call") and part.function_call:
                    fc = part.function_call
                    tool_calls.append({"id": str(uuid4()), "name": fc.name, "input": dict(fc.args)})
        except Exception:
            pass

        if not tool_calls:
            break

        # Append model turn
        contents.append(
            gt.Content(
                role="model", parts=[gt.Part(text=accumulated_text)] if accumulated_text else []
            )
        )

        # Execute tools and append function_response parts in a single user turn
        fn_response_parts: list[gt.Part] = []
        for tc in tool_calls:
            out_str = await _call_tool(tc["name"], tc.get("input", {}), api_keys, emitter)
            try:
                out_dict = json.loads(out_str)
            except Exception:
                out_dict = {"result": out_str}
            fn_response_parts.append(
                gt.Part(function_response=gt.FunctionResponse(name=tc["name"], response=out_dict))
            )
        contents.append(gt.Content(role="user", parts=fn_response_parts))

    return final_text, {"input_tokens": 0, "output_tokens": 0}
