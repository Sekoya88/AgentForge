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
            if p.input_messages:
                msgs = p.input_messages if isinstance(p.input_messages, list) else []
                history.extend(msgs)
            if p.output_messages:
                msgs = p.output_messages if isinstance(p.output_messages, list) else []
                history.extend([m for m in msgs if m.get("role") != "error"])

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
# Background loop
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
    # Build message list in Anthropic format, filtering to plain text turns only
    messages: list[dict] = []
    for h in history:
        role = h.get("role", "user")
        if role in ("user", "assistant"):
            content = h.get("content", "")
            if isinstance(content, str) and content:
                messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": new_message})

    token_usage: dict = {"input_tokens": 0, "output_tokens": 0}
    final_text = ""

    try:
        for _iteration in range(8):  # max 8 tool rounds
            if provider == "anthropic":
                result = await _anthropic_stream(
                    messages, model, api_keys.get("anthropic"), emitter
                )
            elif provider in ("google", "gemini"):
                result = await _gemini_call(messages, model, api_keys.get("google"), emitter)
            else:  # openai default
                result = await _openai_stream(messages, model, api_keys.get("openai"), emitter)

            token_usage["input_tokens"] += result.get("input_tokens", 0)
            token_usage["output_tokens"] += result.get("output_tokens", 0)
            final_text = result.get("text", "")

            if result.get("stop_reason") != "tool_use":
                break

            # Handle tool calls
            tool_calls = result.get("tool_calls", [])
            messages.append({"role": "assistant", "content": result.get("raw_content", final_text)})
            tool_results = await _execute_tools(tool_calls, api_keys, emitter)
            messages.append({"role": "user", "content": tool_results})

        # Persist completion
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
# Provider-specific streaming helpers
# ---------------------------------------------------------------------------


async def _anthropic_stream(
    messages: list[dict],
    model: str,
    api_key: str | None,
    emitter: RedisStreamEmitter,
) -> dict:
    """Stream from Anthropic with tool_use support."""
    if not api_key:
        raise ValueError("Anthropic API key not configured")

    import anthropic

    client = anthropic.AsyncAnthropic(api_key=api_key)

    tools = [
        {
            "name": t["name"],
            "description": t["description"],
            "input_schema": t["input_schema"],
        }
        for t in FORGE_TOOLS
    ]

    accumulated_text = ""
    tool_calls: list[dict] = []
    input_tokens = 0
    output_tokens = 0
    stop_reason = "end_turn"
    raw_content: list = []

    async with client.messages.stream(
        model=model,
        max_tokens=4096,
        system=FORGE_SYSTEM_PROMPT,
        messages=messages,
        tools=tools,
    ) as stream:
        async for event in stream:
            event_type = type(event).__name__
            if event_type == "RawContentBlockDeltaEvent":
                delta = event.delta
                if hasattr(delta, "type") and delta.type == "text_delta":
                    accumulated_text += delta.text
                    await emitter.emit("token", {"text": delta.text})
            elif event_type == "RawMessageDeltaEvent":
                if hasattr(event.delta, "stop_reason"):
                    stop_reason = event.delta.stop_reason or "end_turn"

        final_msg = await stream.get_final_message()
        input_tokens = final_msg.usage.input_tokens
        output_tokens = final_msg.usage.output_tokens
        stop_reason = final_msg.stop_reason or "end_turn"
        raw_content = [b.model_dump() for b in final_msg.content]

        for block in final_msg.content:
            if block.type == "tool_use":
                tool_calls.append(
                    {
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    }
                )

    return {
        "text": accumulated_text,
        "stop_reason": stop_reason,
        "tool_calls": tool_calls,
        "raw_content": raw_content,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }


async def _openai_stream(
    messages: list[dict],
    model: str,
    api_key: str | None,
    emitter: RedisStreamEmitter,
) -> dict:
    """Stream from OpenAI with tool_use support."""
    if not api_key:
        raise ValueError("OpenAI API key not configured")

    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=api_key)

    tools = [
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

    oai_messages = [{"role": "system", "content": FORGE_SYSTEM_PROMPT}, *messages]

    accumulated_text = ""
    tool_calls_raw: dict[int, dict] = {}
    stop_reason = "stop"
    input_tokens = 0
    output_tokens = 0

    stream = await client.chat.completions.create(
        model=model,
        messages=oai_messages,
        tools=tools,
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
            input_tokens = chunk.usage.prompt_tokens
            output_tokens = chunk.usage.completion_tokens

    # Normalise tool calls
    tool_calls: list[dict] = []
    for tc in tool_calls_raw.values():
        try:
            inp = json.loads(tc["arguments"]) if tc["arguments"] else {}
        except json.JSONDecodeError:
            inp = {"raw": tc["arguments"]}
        tool_calls.append({"id": tc["id"], "name": tc["name"], "input": inp})

    eff_stop = "tool_use" if stop_reason == "tool_calls" else "end_turn"

    return {
        "text": accumulated_text,
        "stop_reason": eff_stop,
        "tool_calls": tool_calls,
        "raw_content": accumulated_text,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }


async def _gemini_call(
    messages: list[dict],
    model: str,
    api_key: str | None,
    emitter: RedisStreamEmitter,
) -> dict:
    """Call Gemini with tool support (streaming via SDK)."""
    if not api_key:
        raise ValueError("Google API key not configured")

    import google.generativeai as genai
    from google.generativeai.types import FunctionDeclaration, Tool

    genai.configure(api_key=api_key)

    gemini_tools = Tool(
        function_declarations=[
            FunctionDeclaration(
                name=t["name"],
                description=t["description"],
                parameters=t["input_schema"],
            )
            for t in FORGE_TOOLS
        ]
    )

    gem_model = genai.GenerativeModel(
        model_name=model,
        system_instruction=FORGE_SYSTEM_PROMPT,
        tools=[gemini_tools],
    )

    gemini_messages = []
    for m in messages:
        role = "user" if m["role"] == "user" else "model"
        content = m["content"]
        if isinstance(content, str):
            gemini_messages.append({"role": role, "parts": [content]})

    response = await gem_model.generate_content_async(gemini_messages, stream=True)

    accumulated_text = ""
    async for chunk in response:
        if chunk.text:
            accumulated_text += chunk.text
            await emitter.emit("token", {"text": chunk.text})

    tool_calls: list[dict] = []
    stop_reason = "end_turn"
    try:
        final = response.candidates[0]
        for part in final.content.parts:
            if hasattr(part, "function_call") and part.function_call:
                fc = part.function_call
                tool_calls.append(
                    {
                        "id": str(uuid4()),
                        "name": fc.name,
                        "input": dict(fc.args),
                    }
                )
        if tool_calls:
            stop_reason = "tool_use"
    except Exception:
        pass

    return {
        "text": accumulated_text,
        "stop_reason": stop_reason,
        "tool_calls": tool_calls,
        "raw_content": accumulated_text,
        "input_tokens": 0,
        "output_tokens": 0,
    }


# ---------------------------------------------------------------------------
# Tool execution
# ---------------------------------------------------------------------------


async def _execute_tools(
    tool_calls: list[dict],
    api_keys: dict,
    emitter: RedisStreamEmitter,
) -> list[dict]:
    """Execute tool calls and return tool_result blocks (Anthropic format)."""
    from app.infrastructure.integrations.python_repl import python_repl
    from app.infrastructure.integrations.tavily_search import tavily_search

    results = []
    for tc in tool_calls:
        name = tc["name"]
        inp = tc.get("input", {})
        tc_id = tc.get("id", str(uuid4()))

        await emitter.emit("tool_call", {"name": name, "input": inp})

        try:
            if name == "web_search":
                tavily_key = api_keys.get("tavily")
                if not tavily_key:
                    tool_out: dict = {"error": "Tavily API key not configured. Add it in Settings."}
                else:
                    tool_out = await tavily_search(inp.get("query", ""), tavily_key)
            elif name == "python_repl":
                tool_out = await python_repl(inp.get("code", ""))
            elif name == "list_agents":
                tool_out = {
                    "message": (
                        "Agent listing requires DB access — not yet available in tool context."
                    )
                }
            else:
                tool_out = {"error": f"Unknown tool: {name}"}
        except Exception as e:
            tool_out = {"error": str(e)}

        await emitter.emit("tool_result", {"name": name, "result": tool_out})

        results.append(
            {
                "type": "tool_result",
                "tool_use_id": tc_id,
                "content": json.dumps(tool_out, default=str),
            }
        )

    return results
