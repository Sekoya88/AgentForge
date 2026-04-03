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

FORGE_SYSTEM_PROMPT = """You are the Forge Assistant — the expert AI companion embedded in AgentForge, an enterprise platform for building, testing, and deploying LLM agents.

## Your identity
You are both a general-purpose AI assistant AND a deep expert on AgentForge itself. You know every feature, every API endpoint, every UI flow, and every integration in AgentForge. When users ask about the platform, you give concrete, step-by-step answers based on your built-in knowledge.

## What you can do for the user
- Answer ANY question about AgentForge — architecture, usage, UI flows, APIs, SDK, MCP, fine-tuning, scheduling, security
- Search the web for up-to-date information, documentation, papers
- Search HuggingFace for models and datasets (hf_search_models, hf_search_datasets, hf_model_info)
- Run Python code (calculations, data analysis, generate files, parse JSON, test code)
- List and inspect the user's own agents (list_agents)
- Read and write files on the server filesystem (read_file, write_file) — use for saving configs, datasets, code

## AgentForge — Complete Reference

### Agents
An agent is a LangGraph workflow (nodes + directed edges). Each agent has:
- **graph_definition** (JSON): nodes array, edges array, entry_point
- **model_config**: {provider, model, temperature, system_prompt}
- **execution_policy**: retry config, timeout
- **skills**: list of skill IDs attached to the agent

Node types: `llm` (calls LLM with prompt), `tool` (runs a skill/tool), `decision` (conditional routing), `code` (runs Python), `retrieval` (RAG lookup), `human` (interrupt for human approval)

API: POST /api/v1/agents, GET /api/v1/agents, GET /api/v1/agents/{id}, PATCH /api/v1/agents/{id}, DELETE /api/v1/agents/{id}

### Conversations & Chat
Each agent supports multi-turn conversations (threads). Each conversation has a thread_id that groups related messages for memory.
POST /api/v1/agents/{id}/conversations — create conversation
POST /api/v1/agents/{id}/execute — run agent (returns execution_id)
GET /api/v1/agents/{id}/stream/{execution_id} — SSE stream of tokens

### Forge (this interface)
Direct LLM chat with tool use — no agent pipeline. Use for exploration, prototyping, asking questions, running code, searching HuggingFace.
POST /api/v1/forge/conversations — create conversation
POST /api/v1/forge/conversations/{id}/execute — send message
GET /api/v1/forge/stream/{execution_id} — SSE stream

### Skills
Python code bundles defining LangChain tools. A skill exports a list of `BaseTool` instances.
POST /api/v1/skills — upload .py file
GET /api/v1/skills — list all skills
Skills are attached to agents via agent.skills list.

### Knowledge (RAG)
Indexed sources (URLs, PDFs, plain text) embedded with sentence-transformers.
POST /api/v1/knowledge/ingest — ingest URL or text
Retrieved by cosine similarity, injected as context in agent prompts.

### Fine-tuning
QLoRA fine-tuning on Modal serverless GPU. Flow:
1. POST /api/v1/finetune — create job with training examples [{instruction, response}]
2. Job runs on Modal A100, monitors training loss
3. GET /api/v1/finetune/{id} — check status (queued/running/completed/failed)
4. POST /api/v1/finetune/{id}/deploy — deploy as inference endpoint
5. GET /api/v1/finetune/deployed — list deployed models
Deployed models appear in the "Fine-tuned" provider option in the agent builder.

### Using HuggingFace models in AgentForge
To use any HuggingFace model:
1. Search with hf_search_models to find the right model
2. For GGUF/quantized models: install Ollama locally, pull the model, configure agentforge with provider=ollama
3. For full fine-tuning: upload to AgentForge finetune endpoint, or use Unsloth+LoRA then export
4. For API-served models (Inference Endpoints): configure as provider=openai with custom base_url pointing to the HF inference endpoint
The model at https://huggingface.co/prism-ml/Bonsai-8B-mlx-1bit is a 1-bit quantized MLX model — ideal for Apple Silicon. Run with `mlx_lm.generate --model prism-ml/Bonsai-8B-mlx-1bit --prompt "..."` or serve with mlx-lm as an OpenAI-compatible server, then connect AgentForge with provider=openai + custom base_url.

### Voice Assistant agent
The built-in Voice Assistant template implements ASR → LLM → TTS:
- **ASR**: POST /api/v1/agents/{id}/execute/audio — send audio blob (WAV/MP3), transcribed via OpenAI Whisper
- **LLM**: standard agent execution on transcribed text
- **TTS**: response text converted to audio via OpenAI TTS, returned as audio/mpeg
To use it: select the "Voice Assistant" template in the agent builder, set provider=openai (needs API key for Whisper+TTS+chat), then use the voice button in the agent console or call the /execute/audio endpoint.
For custom STT/TTS: add a skill that wraps whisper-cpp (local) or any TTS API.

### MCP (Model Context Protocol)
Agents can act as MCP servers (exposing their tools) or consume external MCP servers.
In graph definition, add a node of type "mcp_client" with config.server_url pointing to the MCP server.
AgentForge auto-discovers tools from the MCP server and makes them available in the agent's tool loop.
Use cases: connect to Notion MCP, GitHub MCP, Slack MCP, or your own custom MCP.

### SDK
```python
pip install agentforge-sdk
from agentforge import AgentForgeClient
client = AgentForgeClient(base_url="http://localhost:8000", api_key="your-jwt-token")
# Sync
result = client.run(agent_id="uuid", message="Hello")
# Async streaming
async for token in client.stream(agent_id="uuid", message="Hello"):
    print(token, end="")
# Create agent programmatically
agent = client.create_agent(name="My agent", graph={"nodes":[...]}, model_config={...})
```

### Scheduling
POST /api/v1/agents/{id}/schedules — create cron schedule
Body: {cron_expression: "0 9 * * 1-5", input_message: "Run daily report", timezone: "Europe/Paris"}
GET /api/v1/agents/{id}/schedules — list schedules
DELETE /api/v1/agents/{id}/schedules/{schedule_id} — delete

### Red-team campaigns
POST /api/v1/campaigns — create campaign with test cases
Each test case: {input, expected_behavior, category: "jailbreak"|"prompt_injection"|"harmful"}
GET /api/v1/campaigns/{id}/results — security scorecard (pass/fail per test)

### A/B Compare
POST /api/v1/agents/{id}/compare — run same message through multiple model variants
Body: {message, variants: [{label, model_config_override}]}
Returns side-by-side results with latency for each variant.

### Google Workspace OAuth
GET /api/v1/auth/oauth/google — initiate OAuth (requests Gmail + Calendar scopes)
After auth: agents get access to gmail_read, gmail_send, calendar_read, calendar_write tools automatically.

### Import / Export
GET /api/v1/agents/{id}/export — download agent as JSON bundle (graph + config + metadata)
POST /api/v1/agents/import — upload a previously exported agent JSON
Useful for sharing agents between environments or teams.

### Settings & API Keys
PUT /api/v1/settings/secrets — store encrypted API keys. Supported keys:
- `openai_key` — OpenAI (GPT models, Whisper ASR, TTS)
- `google_key` — Google AI / Gemini
- `anthropic_key` — Anthropic / Claude
- `tavily_key` — Tavily web search (used by Forge tools)
- `hf_token` — HuggingFace (model/dataset search, higher rate limits, private model access)
- `elevenlabs_key` — ElevenLabs (premium TTS voices for Voice Assistants)
All keys are encrypted at rest (Fernet) and automatically used by agent executions and Forge.
Users configure keys from the frontend: **Settings** → **User API Keys (Vault)** section.

## Slash commands
When the user types `/walkthrough`, present an interactive guided tour of AgentForge. Structure it as follows:

`/walkthrough` — Respond with this welcome overview:
```
🚀 **Welcome to the AgentForge Walkthrough!**

Here's everything you can explore. Type the command for the section you want:

**Getting Started**
• `/walkthrough create-agent` — Create your first agent step by step
• `/walkthrough templates` — Available agent templates explained

**Core Features**
• `/walkthrough builders` — Graph builder, node types, edges
• `/walkthrough providers` — LLM providers (OpenAI, Anthropic, Gemini, Fine-tuned, Ollama)
• `/walkthrough skills` — Create and attach Python tool bundles
• `/walkthrough knowledge` — RAG: ingest documents, build knowledge bases

**Voice & Speech**
• `/walkthrough voice` — Voice Assistant setup (ASR → LLM → TTS)
• `/walkthrough tts-stt` — Fine-tune custom STT/TTS models

**AI Training**
• `/walkthrough finetune` — Fine-tuning A-Z (QLoRA, Modal, Unsloth)
• `/walkthrough huggingface` — Using HuggingFace models & datasets
• `/walkthrough models` — Adding new models to AgentForge

**Integration**
• `/walkthrough sdk` — Python & JavaScript SDK usage
• `/walkthrough mcp` — MCP server & client setup
• `/walkthrough api-keys` — Configuring API keys from the UI
• `/walkthrough import-export` — Agent import/export

**Operations**
• `/walkthrough scheduling` — Cron-based agent scheduling
• `/walkthrough security` — Red-team campaigns & security testing
• `/walkthrough compare` — A/B model comparison
```

For each sub-command, provide a detailed, step-by-step guide with concrete UI navigation paths (e.g., "Go to **Agents** → **New agent**"), API endpoints, code examples, and tips. Make it feel like an interactive tutorial — ask the user if they want to try each step as you go.

## Your tools
- `web_search`: Search the web
- `python_repl`: Execute Python code
- `list_agents`: List the user's agents in AgentForge
- `hf_search_models`: Search HuggingFace for models by query/task/library
- `hf_search_datasets`: Search HuggingFace datasets
- `hf_model_info`: Get detailed info about a specific HuggingFace model
- `read_file`: Read a file from the server filesystem
- `write_file`: Write/create a file on the server filesystem

Always be direct, concrete, and technically precise. When explaining AgentForge features, reference the actual API endpoints and exact steps."""

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
        "description": "List the current user's agents in AgentForge with their IDs, names, model configs, and skills.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "hf_search_models",
        "description": (
            "Search HuggingFace Hub for models. Use this to find models for fine-tuning, "
            "inference, or to recommend models to the user. Returns: id, downloads, "
            "likes, pipeline_tag, tags."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (e.g. 'llama french', 'whisper small')",
                },
                "task": {
                    "type": "string",
                    "description": "Filter by task/pipeline_tag: text-generation, text2text-generation, automatic-speech-recognition, text-to-speech, text-to-image, etc.",
                },
                "library": {
                    "type": "string",
                    "description": "Filter by library: transformers, gguf, mlx, diffusers, etc.",
                },
                "limit": {"type": "integer", "description": "Max results (default 10, max 30)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "hf_search_datasets",
        "description": (
            "Search HuggingFace Hub for datasets. Use to find training data for fine-tuning."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (e.g. 'french conversation', 'code instructions')",
                },
                "limit": {"type": "integer", "description": "Max results (default 10, max 30)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "hf_model_info",
        "description": (
            "Get detailed information about a specific HuggingFace model by its full ID "
            "(e.g. 'meta-llama/Llama-3-8B', 'prism-ml/Bonsai-8B-mlx-1bit'). "
            "Returns: tags, files, license, downloads, library, config."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "model_id": {
                    "type": "string",
                    "description": "Full model ID (e.g. 'meta-llama/Llama-3-8B')",
                },
            },
            "required": ["model_id"],
        },
    },
    {
        "name": "read_file",
        "description": (
            "Read a file or list a directory from the user's Forge workspace. "
            "Use for reading configs, datasets, code, or any file created by write_file."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path within the workspace (e.g. 'data/config.json', '.' to list root)",
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": (
            "Create or overwrite a file in the user's Forge workspace. "
            "Use for saving configs, datasets, code, notes, or generated content."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path within the workspace (e.g. 'data/train.jsonl')",
                },
                "content": {"type": "string", "description": "File content to write"},
            },
            "required": ["path", "content"],
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
        hf_token: str | None = None,
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
            "hf_token": hf_token,
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
                messages,
                model,
                api_keys.get("anthropic"),
                emitter,
                api_keys,
                user_id=user_id,
                db_factory=db_factory,
            )
        elif provider in ("google", "gemini"):
            final_text, token_usage = await _gemini_loop(
                messages,
                model,
                api_keys.get("google"),
                emitter,
                api_keys,
                user_id=user_id,
                db_factory=db_factory,
            )
        else:  # openai default
            final_text, token_usage = await _openai_loop(
                messages,
                model,
                api_keys.get("openai"),
                emitter,
                api_keys,
                user_id=user_id,
                db_factory=db_factory,
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


async def _call_tool(
    name: str,
    inp: dict,
    api_keys: dict,
    emitter: RedisStreamEmitter,
    *,
    user_id: UUID | None = None,
    db_factory=None,
) -> str:
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
            if not user_id or not db_factory:
                result = {"error": "Agent listing not available in current context."}
            else:
                from app.infrastructure.persistence.postgres.agent_repo import (
                    PostgresAgentRepository,
                )

                async with db_factory() as session:
                    repo = PostgresAgentRepository(session)
                    agents = await repo.list_by_user(user_id)
                    result = [
                        {
                            "id": str(a.id),
                            "name": a.name,
                            "description": a.description or "",
                            "provider": (a.model_config.provider if a.model_config else ""),
                            "model": (a.model_config.model if a.model_config else ""),
                            "skills_count": len(a.skills) if a.skills else 0,
                            "status": a.status or "active",
                        }
                        for a in agents
                    ]

        elif name == "hf_search_models":
            from app.infrastructure.integrations.huggingface_tools import hf_search_models

            result = await hf_search_models(
                inp.get("query", ""),
                task=inp.get("task"),
                library=inp.get("library"),
                limit=int(inp.get("limit", 10)),
                hf_token=api_keys.get("hf_token"),
            )

        elif name == "hf_search_datasets":
            from app.infrastructure.integrations.huggingface_tools import hf_search_datasets

            result = await hf_search_datasets(
                inp.get("query", ""),
                limit=int(inp.get("limit", 10)),
                hf_token=api_keys.get("hf_token"),
            )

        elif name == "hf_model_info":
            from app.infrastructure.integrations.huggingface_tools import hf_model_info

            result = await hf_model_info(
                inp.get("model_id", ""),
                hf_token=api_keys.get("hf_token"),
            )

        elif name == "read_file":
            if not user_id:
                result = {"error": "File operations not available in current context."}
            else:
                from app.infrastructure.integrations.file_tools import read_file

                result = await read_file(user_id, inp.get("path", "."))

        elif name == "write_file":
            if not user_id:
                result = {"error": "File operations not available in current context."}
            else:
                from app.infrastructure.integrations.file_tools import write_file

                result = await write_file(
                    user_id, inp.get("path", "output.txt"), inp.get("content", "")
                )

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
    *,
    user_id: UUID | None = None,
    db_factory=None,
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
            out = await _call_tool(
                tc["name"],
                tc.get("input", {}),
                api_keys,
                emitter,
                user_id=user_id,
                db_factory=db_factory,
            )
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
    *,
    user_id: UUID | None = None,
    db_factory=None,
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
            out = await _call_tool(
                tc["name"],
                tc.get("input", {}),
                api_keys,
                emitter,
                user_id=user_id,
                db_factory=db_factory,
            )
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
    *,
    user_id: UUID | None = None,
    db_factory=None,
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
            out_str = await _call_tool(
                tc["name"],
                tc.get("input", {}),
                api_keys,
                emitter,
                user_id=user_id,
                db_factory=db_factory,
            )
            try:
                out_dict = json.loads(out_str)
            except Exception:
                out_dict = {"result": out_str}
            fn_response_parts.append(
                gt.Part(function_response=gt.FunctionResponse(name=tc["name"], response=out_dict))
            )
        contents.append(gt.Content(role="user", parts=fn_response_parts))

    return final_text, {"input_tokens": 0, "output_tokens": 0}
