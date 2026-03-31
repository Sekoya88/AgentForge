# Phase N3 — Speech ASR + TTS Implementation Plan

> **Statut : terminé** (providers, orchestrateur, `/execute/audio`, migration `output_audio_b64`, SDK `asr_node`/`tts_node`, UI builder + lecteur audio). *Note* : l’API audio livrée est **multipart**, pas du streaming SSE pour le corps audio. Les providers **HTTP fine-tuned** (`finetuned_whisper` / `finetuned_tts`) et `GET /api/v1/speech/deployed` relèvent du **plan N5** (speech Modal) — voir `2026-03-30-N5-speech-training-modal.md`.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `asr` and `tts` node types to AgentForge so agents can transcribe audio input (OpenAI Whisper) and synthesize spoken output (OpenAI TTS or ElevenLabs), with a `/execute/audio` multipart endpoint, SDK builder helpers, and frontend palette + audio player.

**Architecture:** Speech providers are Protocol classes behind ports (`ASRProvider`, `TTSProvider`). The LangGraph orchestrator handles `asr`/`tts` node types by calling these providers and passing audio via a new `audio_b64` field in `_State`. The SDK Python builder adds `asr_node()` / `tts_node()` convenience methods; `agent.py` handles these node types locally. The frontend adds ASR/TTS palette buttons, config panels, and an inline `<audio>` player in ExecutionLog.

**Tech Stack:** `openai>=1.50` (direct SDK for `audio.transcriptions` + `audio.speech`), `elevenlabs>=1.0`, FastAPI multipart (`python-multipart` already in deps), React/Next.js 15, `@xyflow/react` (already in frontend).

---

## File structure

**Create:**
- `backend/app/infrastructure/speech/__init__.py`
- `backend/app/infrastructure/speech/ports.py` — `ASRProvider` + `TTSProvider` protocols
- `backend/app/infrastructure/speech/providers/__init__.py`
- `backend/app/infrastructure/speech/providers/openai_whisper.py`
- `backend/app/infrastructure/speech/providers/openai_tts.py`
- `backend/app/infrastructure/speech/providers/elevenlabs_tts.py`
- `backend/tests/test_speech.py`
- `sdk/tests/unit/test_speech_builder.py`

**Modify:**
- `backend/pyproject.toml` — add `openai>=1.50.0`, `elevenlabs>=1.0`
- `backend/app/infrastructure/orchestration/langgraph_orchestrator.py` — `_State.audio_b64`, `asr`/`tts` node handlers
- `backend/app/api/v1/agents.py` — add `POST /{agent_id}/execute/audio`
- `sdk/src/agentforge/builder.py` — add `asr_node()`, `tts_node()`
- `sdk/src/agentforge/agent.py` — add `asr`/`tts` handling in `_create_step_function`
- `sdk/src/agentforge/__init__.py` — no change needed (methods are on existing class)
- `frontend/src/app/agents/[id]/builder/page.tsx` — `NodeKind`, config panels, palette
- `frontend/src/components/execution/ExecutionLog.tsx` — inline `<audio>` for `audio_b64` events
- `frontend/src/app/agents/[id]/page.tsx` — VoiceTestButton (check if exists first)

---

## Task 1: Dependencies + Speech Ports

**Files:**
- Modify: `backend/pyproject.toml`
- Create: `backend/app/infrastructure/speech/__init__.py`
- Create: `backend/app/infrastructure/speech/ports.py`
- Create: `backend/app/infrastructure/speech/providers/__init__.py`

- [ ] **Step 1: Add dependencies to backend pyproject.toml**

Open `backend/pyproject.toml`. In the `dependencies` list, after `"langchain-ollama>=0.3.0"`, add:

```toml
    "openai>=1.50.0",
    "elevenlabs>=1.0.0",
```

- [ ] **Step 2: Create speech module init files**

Create `backend/app/infrastructure/speech/__init__.py`:
```python
```
(empty file)

Create `backend/app/infrastructure/speech/providers/__init__.py`:
```python
```
(empty file)

- [ ] **Step 3: Write the failing test for ports**

Create `backend/tests/test_speech.py`:
```python
"""Tests for speech providers and orchestrator nodes."""
import base64
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def test_ports_import():
    from app.infrastructure.speech.ports import ASRProvider, TTSProvider
    assert ASRProvider is not None
    assert TTSProvider is not None


def test_asr_provider_is_protocol():
    from app.infrastructure.speech.ports import ASRProvider
    import typing
    assert hasattr(ASRProvider, "__protocol_attrs__") or hasattr(ASRProvider, "transcribe")


def test_tts_provider_is_protocol():
    from app.infrastructure.speech.ports import TTSProvider
    assert hasattr(TTSProvider, "synthesize")
```

- [ ] **Step 4: Run test to verify it fails**

```bash
cd backend && uv run --with pytest pytest tests/test_speech.py::test_ports_import -v
```
Expected: `ModuleNotFoundError: No module named 'app.infrastructure.speech.ports'`

- [ ] **Step 5: Implement ports.py**

Create `backend/app/infrastructure/speech/ports.py`:
```python
from typing import Protocol, runtime_checkable


@runtime_checkable
class ASRProvider(Protocol):
    """Transcribes audio bytes to text."""

    async def transcribe(
        self,
        audio_bytes: bytes,
        language: str | None = None,
        filename: str = "audio.webm",
    ) -> str:
        """Return transcribed text."""
        ...


@runtime_checkable
class TTSProvider(Protocol):
    """Synthesizes text to audio bytes (MP3)."""

    async def synthesize(
        self,
        text: str,
        voice: str = "nova",
    ) -> bytes:
        """Return MP3 bytes."""
        ...
```

- [ ] **Step 6: Run test to verify it passes**

```bash
cd backend && uv run --with pytest pytest tests/test_speech.py::test_ports_import tests/test_speech.py::test_asr_provider_is_protocol tests/test_speech.py::test_tts_provider_is_protocol -v
```
Expected: 3 passed

- [ ] **Step 7: Commit**

```bash
git add backend/pyproject.toml backend/app/infrastructure/speech/ backend/tests/test_speech.py
git commit -m "feat(speech): add speech ports and module skeleton"
```

---

## Task 2: OpenAI Whisper ASR Provider

**Files:**
- Create: `backend/app/infrastructure/speech/providers/openai_whisper.py`
- Modify: `backend/tests/test_speech.py`

- [ ] **Step 1: Write failing test**

Add to `backend/tests/test_speech.py`:
```python
@pytest.mark.asyncio
async def test_openai_whisper_transcribes():
    from app.infrastructure.speech.providers.openai_whisper import OpenAIWhisperASR

    fake_audio = b"RIFF" + b"\x00" * 40  # fake WAV header

    mock_client = MagicMock()
    mock_client.audio.transcriptions.create = AsyncMock(
        return_value=MagicMock(text="Bonjour le monde")
    )

    provider = OpenAIWhisperASR(client=mock_client)
    result = await provider.transcribe(fake_audio, language="fr")
    assert result == "Bonjour le monde"
    mock_client.audio.transcriptions.create.assert_called_once()


@pytest.mark.asyncio
async def test_openai_whisper_passes_language():
    from app.infrastructure.speech.providers.openai_whisper import OpenAIWhisperASR

    mock_client = MagicMock()
    mock_client.audio.transcriptions.create = AsyncMock(
        return_value=MagicMock(text="Hello")
    )
    provider = OpenAIWhisperASR(client=mock_client)
    await provider.transcribe(b"audio", language="en")
    call_kwargs = mock_client.audio.transcriptions.create.call_args.kwargs
    assert call_kwargs.get("language") == "en"


@pytest.mark.asyncio
async def test_openai_whisper_default_model():
    from app.infrastructure.speech.providers.openai_whisper import OpenAIWhisperASR

    mock_client = MagicMock()
    mock_client.audio.transcriptions.create = AsyncMock(return_value=MagicMock(text="ok"))
    provider = OpenAIWhisperASR(client=mock_client)
    await provider.transcribe(b"audio")
    call_kwargs = mock_client.audio.transcriptions.create.call_args.kwargs
    assert call_kwargs.get("model") == "whisper-1"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && uv run --with pytest pytest tests/test_speech.py::test_openai_whisper_transcribes -v
```
Expected: `ImportError: cannot import name 'OpenAIWhisperASR'`

- [ ] **Step 3: Implement OpenAI Whisper provider**

Create `backend/app/infrastructure/speech/providers/openai_whisper.py`:
```python
import io
from typing import Any


class OpenAIWhisperASR:
    """ASR provider using OpenAI Whisper API."""

    def __init__(self, client: Any = None, api_key: str | None = None) -> None:
        if client is not None:
            self._client = client
        else:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(api_key=api_key)

    async def transcribe(
        self,
        audio_bytes: bytes,
        language: str | None = None,
        filename: str = "audio.webm",
    ) -> str:
        file_tuple = (filename, io.BytesIO(audio_bytes))
        kwargs: dict[str, Any] = {"model": "whisper-1", "file": file_tuple}
        if language:
            kwargs["language"] = language
        result = await self._client.audio.transcriptions.create(**kwargs)
        return str(result.text)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && uv run --with pytest pytest tests/test_speech.py::test_openai_whisper_transcribes tests/test_speech.py::test_openai_whisper_passes_language tests/test_speech.py::test_openai_whisper_default_model -v
```
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/infrastructure/speech/providers/openai_whisper.py backend/tests/test_speech.py
git commit -m "feat(speech): add OpenAI Whisper ASR provider"
```

---

## Task 3: OpenAI TTS Provider

**Files:**
- Create: `backend/app/infrastructure/speech/providers/openai_tts.py`
- Modify: `backend/tests/test_speech.py`

- [ ] **Step 1: Write failing tests**

Add to `backend/tests/test_speech.py`:
```python
@pytest.mark.asyncio
async def test_openai_tts_synthesizes():
    from app.infrastructure.speech.providers.openai_tts import OpenAITTS

    mock_client = MagicMock()
    fake_mp3 = b"ID3" + b"\x00" * 50
    mock_response = MagicMock()
    mock_response.read = AsyncMock(return_value=fake_mp3)
    mock_client.audio.speech.create = AsyncMock(return_value=mock_response)

    provider = OpenAITTS(client=mock_client)
    result = await provider.synthesize("Hello world", voice="nova")
    assert result == fake_mp3


@pytest.mark.asyncio
async def test_openai_tts_default_voice():
    from app.infrastructure.speech.providers.openai_tts import OpenAITTS

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.read = AsyncMock(return_value=b"mp3")
    mock_client.audio.speech.create = AsyncMock(return_value=mock_resp)

    provider = OpenAITTS(client=mock_client)
    await provider.synthesize("test")
    call_kwargs = mock_client.audio.speech.create.call_args.kwargs
    assert call_kwargs.get("voice") == "nova"
    assert call_kwargs.get("model") in ("tts-1", "tts-1-hd")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && uv run --with pytest pytest tests/test_speech.py::test_openai_tts_synthesizes -v
```
Expected: `ImportError: cannot import name 'OpenAITTS'`

- [ ] **Step 3: Implement OpenAI TTS provider**

Create `backend/app/infrastructure/speech/providers/openai_tts.py`:
```python
from typing import Any


class OpenAITTS:
    """TTS provider using OpenAI speech API."""

    def __init__(
        self,
        client: Any = None,
        api_key: str | None = None,
        model: str = "tts-1",
    ) -> None:
        self._model = model
        if client is not None:
            self._client = client
        else:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(api_key=api_key)

    async def synthesize(self, text: str, voice: str = "nova") -> bytes:
        response = await self._client.audio.speech.create(
            model=self._model,
            voice=voice,
            input=text,
            response_format="mp3",
        )
        return await response.read()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && uv run --with pytest pytest tests/test_speech.py::test_openai_tts_synthesizes tests/test_speech.py::test_openai_tts_default_voice -v
```
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/infrastructure/speech/providers/openai_tts.py backend/tests/test_speech.py
git commit -m "feat(speech): add OpenAI TTS provider"
```

---

## Task 4: ElevenLabs TTS Provider

**Files:**
- Create: `backend/app/infrastructure/speech/providers/elevenlabs_tts.py`
- Modify: `backend/tests/test_speech.py`

- [ ] **Step 1: Write failing tests**

Add to `backend/tests/test_speech.py`:
```python
@pytest.mark.asyncio
async def test_elevenlabs_tts_synthesizes():
    from app.infrastructure.speech.providers.elevenlabs_tts import ElevenLabsTTS

    mock_client = MagicMock()
    fake_mp3 = b"EL_MP3" + b"\x00" * 20
    mock_client.generate = AsyncMock(return_value=fake_mp3)

    provider = ElevenLabsTTS(client=mock_client)
    result = await provider.synthesize("Bonjour", voice="Rachel")
    assert result == fake_mp3


@pytest.mark.asyncio
async def test_elevenlabs_tts_passes_voice():
    from app.infrastructure.speech.providers.elevenlabs_tts import ElevenLabsTTS

    mock_client = MagicMock()
    mock_client.generate = AsyncMock(return_value=b"mp3")
    provider = ElevenLabsTTS(client=mock_client)
    await provider.synthesize("Hello", voice="Bella")
    call_kwargs = mock_client.generate.call_args.kwargs
    assert call_kwargs.get("voice") == "Bella"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && uv run --with pytest pytest tests/test_speech.py::test_elevenlabs_tts_synthesizes -v
```
Expected: `ImportError: cannot import name 'ElevenLabsTTS'`

- [ ] **Step 3: Implement ElevenLabs TTS provider**

Create `backend/app/infrastructure/speech/providers/elevenlabs_tts.py`:
```python
from typing import Any


class ElevenLabsTTS:
    """TTS provider using ElevenLabs API."""

    def __init__(
        self,
        client: Any = None,
        api_key: str | None = None,
    ) -> None:
        if client is not None:
            self._client = client
        else:
            from elevenlabs import AsyncElevenLabs
            self._client = AsyncElevenLabs(api_key=api_key)

    async def synthesize(self, text: str, voice: str = "Rachel") -> bytes:
        result = await self._client.generate(
            text=text,
            voice=voice,
            model="eleven_multilingual_v2",
        )
        # elevenlabs returns bytes directly or an async iterator
        if isinstance(result, bytes):
            return result
        # async generator case
        chunks: list[bytes] = []
        async for chunk in result:
            chunks.append(chunk)
        return b"".join(chunks)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && uv run --with pytest pytest tests/test_speech.py::test_elevenlabs_tts_synthesizes tests/test_speech.py::test_elevenlabs_tts_passes_voice -v
```
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/infrastructure/speech/providers/elevenlabs_tts.py backend/tests/test_speech.py
git commit -m "feat(speech): add ElevenLabs TTS provider"
```

---

## Task 5: Orchestrator — `audio_b64` state + ASR/TTS node handlers

**Files:**
- Modify: `backend/app/infrastructure/orchestration/langgraph_orchestrator.py`
- Modify: `backend/tests/test_speech.py`

The orchestrator currently has:
```python
class _State(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
```

We add `audio_b64: str | None` and two new `if ntype ==` branches after the existing `if ntype == "subagent":` block.

- [ ] **Step 1: Write failing tests**

Add to `backend/tests/test_speech.py`:
```python
@pytest.mark.asyncio
async def test_asr_node_transcribes_and_injects_message():
    """ASR node reads audio_b64, transcribes, returns HumanMessage."""
    from unittest.mock import AsyncMock, MagicMock, patch
    import base64
    from langchain_core.messages import HumanMessage

    fake_audio = base64.b64encode(b"fakeaudio").decode()

    with patch(
        "app.infrastructure.orchestration.langgraph_orchestrator._build_asr_provider"
    ) as mock_build:
        mock_provider = MagicMock()
        mock_provider.transcribe = AsyncMock(return_value="hello world")
        mock_build.return_value = mock_provider

        from app.infrastructure.orchestration.langgraph_orchestrator import _run_asr_node

        result = await _run_asr_node(
            state={"messages": [], "audio_b64": fake_audio},
            cfg={"provider": "openai_whisper", "language": "en"},
            settings=MagicMock(openai_api_key="sk-test"),
        )
    assert len(result["messages"]) == 1
    assert isinstance(result["messages"][0], HumanMessage)
    assert "hello world" in result["messages"][0].content


@pytest.mark.asyncio
async def test_tts_node_synthesizes_last_ai_message():
    """TTS node reads last AIMessage, synthesizes, returns audio_b64."""
    import base64
    from unittest.mock import AsyncMock, MagicMock, patch
    from langchain_core.messages import AIMessage

    fake_mp3 = b"MP3DATA"

    with patch(
        "app.infrastructure.orchestration.langgraph_orchestrator._build_tts_provider"
    ) as mock_build:
        mock_provider = MagicMock()
        mock_provider.synthesize = AsyncMock(return_value=fake_mp3)
        mock_build.return_value = mock_provider

        from app.infrastructure.orchestration.langgraph_orchestrator import _run_tts_node

        result = await _run_tts_node(
            state={"messages": [AIMessage(content="Hello!")], "audio_b64": None},
            cfg={"provider": "openai_tts", "voice": "nova"},
            settings=MagicMock(openai_api_key="sk-test"),
        )

    assert "audio_b64" in result
    decoded = base64.b64decode(result["audio_b64"])
    assert decoded == fake_mp3
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && uv run --with pytest pytest tests/test_speech.py::test_asr_node_transcribes_and_injects_message tests/test_speech.py::test_tts_node_synthesizes_last_ai_message -v
```
Expected: `ImportError: cannot import name '_run_asr_node'`

- [ ] **Step 3: Add `audio_b64` to `_State` in orchestrator**

In `backend/app/infrastructure/orchestration/langgraph_orchestrator.py`, find:

```python
class _State(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
```

Replace with:
```python
class _State(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    audio_b64: str | None
```

- [ ] **Step 4: Add provider factory functions and node helpers**

In `backend/app/infrastructure/orchestration/langgraph_orchestrator.py`, after the imports block (after `from app.infrastructure.orchestration.llm_invoke import ...`), add:

```python
from app.config import Settings as _Settings


def _build_asr_provider(cfg: dict, settings: _Settings):
    provider = cfg.get("provider", "openai_whisper")
    if provider == "openai_whisper":
        from app.infrastructure.speech.providers.openai_whisper import OpenAIWhisperASR
        return OpenAIWhisperASR(api_key=settings.openai_api_key)
    raise ValueError(f"Unknown ASR provider: {provider!r}")


def _build_tts_provider(cfg: dict, settings: _Settings):
    provider = cfg.get("provider", "openai_tts")
    if provider == "openai_tts":
        from app.infrastructure.speech.providers.openai_tts import OpenAITTS
        return OpenAITTS(api_key=settings.openai_api_key)
    if provider == "elevenlabs":
        from app.infrastructure.speech.providers.elevenlabs_tts import ElevenLabsTTS
        return ElevenLabsTTS(api_key=getattr(settings, "elevenlabs_api_key", None))
    raise ValueError(f"Unknown TTS provider: {provider!r}")


async def _run_asr_node(state: dict, cfg: dict, settings) -> dict:
    import base64
    from langchain_core.messages import HumanMessage
    audio_b64 = state.get("audio_b64") or ""
    audio_bytes = base64.b64decode(audio_b64) if audio_b64 else b""
    provider = _build_asr_provider(cfg, settings)
    language = cfg.get("language") or None
    transcript = await provider.transcribe(audio_bytes, language=language)
    return {"messages": [HumanMessage(content=transcript)], "audio_b64": None}


async def _run_tts_node(state: dict, cfg: dict, settings) -> dict:
    import base64
    from langchain_core.messages import AIMessage
    last_ai = next(
        (m for m in reversed(state.get("messages", [])) if isinstance(m, AIMessage)),
        None,
    )
    text = str(last_ai.content) if last_ai else ""
    provider = _build_tts_provider(cfg, settings)
    voice = cfg.get("voice", "nova")
    mp3_bytes = await provider.synthesize(text, voice=voice)
    return {"audio_b64": base64.b64encode(mp3_bytes).decode()}
```

- [ ] **Step 5: Wire ASR/TTS into the node dispatch**

In `langgraph_orchestrator.py`, find the `if ntype == "subagent":` block. After the entire subagent block (it ends with a `return {"messages": [msg]}`), add before the final `return` or the next `if ntype`:

```python
        if ntype == "asr":
            cfg = spec.get("config") or {}
            result = await _run_asr_node(state, cfg, settings)
            dur = int((time.perf_counter() - t0) * 1000)
            await bus.emit(
                "agent_end",
                {
                    "agent_name": node_id,
                    "duration_ms": dur,
                    "output_preview": str(result.get("messages", [{}])[-1])[:200],
                },
            )
            return result
        if ntype == "tts":
            cfg = spec.get("config") or {}
            result = await _run_tts_node(state, cfg, settings)
            dur = int((time.perf_counter() - t0) * 1000)
            await bus.emit(
                "agent_end",
                {
                    "agent_name": node_id,
                    "duration_ms": dur,
                    "output_preview": f"[audio:{len(result.get('audio_b64',''))} chars b64]",
                },
            )
            return result
```

Also check the `_build_node_step` function signature — it receives `settings` already; if not, locate where settings is passed and thread it through the same way as `openai_key`.

- [ ] **Step 6: Run tests to verify they pass**

```bash
cd backend && uv run --with pytest pytest tests/test_speech.py::test_asr_node_transcribes_and_injects_message tests/test_speech.py::test_tts_node_synthesizes_last_ai_message -v
```
Expected: 2 passed

- [ ] **Step 7: Commit**

```bash
git add backend/app/infrastructure/orchestration/langgraph_orchestrator.py backend/tests/test_speech.py
git commit -m "feat(speech): add asr/tts node handlers in orchestrator"
```

---

## Task 6: API — `POST /{agent_id}/execute/audio` Endpoint

**Files:**
- Modify: `backend/app/api/v1/agents.py`
- Modify: `backend/tests/test_speech.py`

- [ ] **Step 1: Write failing test**

Add to `backend/tests/test_speech.py`:
```python
@pytest.mark.asyncio
async def test_execute_audio_endpoint_requires_file(async_client, auth_headers):
    """POST /execute/audio without file returns 422."""
    resp = await async_client.post(
        "/api/v1/agents/00000000-0000-0000-0000-000000000001/execute/audio",
        headers=auth_headers,
    )
    assert resp.status_code == 422
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && uv run --with pytest pytest tests/test_speech.py::test_execute_audio_endpoint_requires_file -v
```
Expected: 404 (route doesn't exist yet)

- [ ] **Step 3: Add the endpoint**

In `backend/app/api/v1/agents.py`, add these imports at the top (after existing imports):
```python
from fastapi import UploadFile, File, Form
```

Then add the route after the existing `execute_agent` route (around line 190):

```python
@router.post("/{agent_id}/execute/audio")
async def execute_agent_audio(
    agent_id: str,
    file: UploadFile = File(..., description="Audio file (webm, mp3, wav, m4a)"),
    config: str = Form(default="{}"),
    current_user=Depends(get_current_user),
    agent_service: AgentService = Depends(get_agent_service),
):
    """Execute agent with audio input — returns SSE stream with transcription + optional audio."""
    import base64
    import json as _json
    from sse_starlette.sse import EventSourceResponse

    try:
        cfg = _json.loads(config)
    except Exception:
        cfg = {}

    audio_bytes = await file.read()
    audio_b64 = base64.b64encode(audio_bytes).decode()

    try:
        agent = await agent_service.get_agent(UUID(agent_id), current_user.id)
    except Exception:
        raise HTTPException(status_code=404, detail="Agent not found")

    execution_input = cfg.get("input", {})
    messages = execution_input.get("messages", [{"role": "user", "content": ""}])

    async def event_stream():
        try:
            result = await agent_service.execute_agent(
                agent_id=UUID(agent_id),
                user_id=current_user.id,
                messages=messages,
                extra_state={"audio_b64": audio_b64},
            )
            yield {"event": "transcription", "data": _json.dumps({"text": result.get("transcript", "")})}
            if result.get("audio_b64"):
                yield {"event": "audio", "data": _json.dumps({"audio_b64": result["audio_b64"]})}
            yield {"event": "done", "data": "{}"}
        except Exception as exc:
            yield {"event": "error", "data": _json.dumps({"message": str(exc)})}

    return EventSourceResponse(event_stream())
```

**Note:** `agent_service.execute_agent` may need a new `extra_state` parameter. Check the existing `execute_agent` use case. If it doesn't support `extra_state`, use `execute_agent` with `messages` as-is and handle audio_b64 at orchestrator level by patching the initial state. The simplest approach that works: pass audio_b64 as part of the first message content if the agent has an ASR node as entry point — or better, add `extra_state: dict | None = None` to `AgentService.execute_agent` and thread it through to the orchestrator `ainvoke` call.

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && uv run --with pytest pytest tests/test_speech.py::test_execute_audio_endpoint_requires_file -v
```
Expected: 1 passed (422 returned for missing file)

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/v1/agents.py backend/tests/test_speech.py
git commit -m "feat(speech): add POST /execute/audio endpoint"
```

---

## Task 7: SDK Python — `asr_node()`, `tts_node()`, local execution

**Files:**
- Modify: `sdk/src/agentforge/builder.py`
- Modify: `sdk/src/agentforge/agent.py`

- [ ] **Step 1: Write failing tests**

Create `sdk/tests/unit/test_speech_builder.py`:
```python
"""Tests for ASR/TTS node builder methods."""
import pytest
from agentforge.builder import AgentBuilder


def test_asr_node_adds_correct_type():
    agent = (
        AgentBuilder("VoiceAgent")
        .asr_node("transcribe", provider="openai_whisper", language="fr")
        .build()
    )
    nodes = agent.graph_definition.nodes
    assert len(nodes) == 1
    assert nodes[0].type == "asr"
    assert nodes[0].config["provider"] == "openai_whisper"
    assert nodes[0].config["language"] == "fr"


def test_tts_node_adds_correct_type():
    agent = (
        AgentBuilder("VoiceAgent")
        .tts_node("speak", provider="openai_tts", voice="shimmer")
        .build()
    )
    nodes = agent.graph_definition.nodes
    assert nodes[0].type == "tts"
    assert nodes[0].config["voice"] == "shimmer"


def test_asr_node_sets_entry_point():
    agent = (
        AgentBuilder("VoiceAgent")
        .asr_node("transcribe")
        .llm_node("reason")
        .edge("transcribe", "reason")
        .build()
    )
    assert agent.graph_definition.entry_point == "transcribe"


def test_tts_node_defaults():
    agent = AgentBuilder("V").tts_node("speak").build()
    cfg = agent.graph_definition.nodes[0].config
    assert cfg.get("provider") == "openai_tts"
    assert cfg.get("voice") == "nova"


def test_asr_node_defaults():
    agent = AgentBuilder("V").asr_node("transcribe").build()
    cfg = agent.graph_definition.nodes[0].config
    assert cfg.get("provider") == "openai_whisper"


def test_full_voice_pipeline_graph():
    agent = (
        AgentBuilder("VoiceAssistant")
        .model("openai", "gpt-4o")
        .asr_node("transcribe", provider="openai_whisper", language="fr")
        .llm_node("reason", system_prompt="Tu es un assistant vocal.")
        .tts_node("speak", provider="openai_tts", voice="nova")
        .edge("transcribe", "reason")
        .edge("reason", "speak")
        .build()
    )
    assert len(agent.graph_definition.nodes) == 3
    assert len(agent.graph_definition.edges) == 2
    types = [n.type for n in agent.graph_definition.nodes]
    assert types == ["asr", "llm", "tts"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd sdk && uv run --with pytest pytest tests/unit/test_speech_builder.py -v
```
Expected: `AttributeError: 'AgentBuilder' object has no attribute 'asr_node'`

- [ ] **Step 3: Add `asr_node()` and `tts_node()` to builder**

In `sdk/src/agentforge/builder.py`, after the `tool_node` method (around line 116), add:

```python
    def asr_node(
        self,
        id: str,
        provider: str = "openai_whisper",
        language: str | None = None,
    ) -> "AgentBuilder":
        config: Dict[str, Any] = {"provider": provider}
        if language:
            config["language"] = language
        if not self._entry_point:
            self._entry_point = id
        self._nodes.append(NodeConfig(id=id, type="asr", config=config))
        return self

    def tts_node(
        self,
        id: str,
        provider: str = "openai_tts",
        voice: str = "nova",
    ) -> "AgentBuilder":
        config: Dict[str, Any] = {"provider": provider, "voice": voice}
        if not self._entry_point:
            self._entry_point = id
        self._nodes.append(NodeConfig(id=id, type="tts", config=config))
        return self
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd sdk && uv run --with pytest pytest tests/unit/test_speech_builder.py -v
```
Expected: 6 passed

- [ ] **Step 5: Add ASR/TTS handling in `agent.py`**

In `sdk/src/agentforge/agent.py`, in `_create_step_function`, after the `elif node_type == "interrupt":` block and before `elif node_type in _NODE_REGISTRY:`, add:

```python
            elif node_type == "asr":
                import base64
                audio_b64 = state.get("audio_b64", "")
                if not audio_b64:
                    return {"messages": [AIMessage(content="[asr] No audio_b64 in state.")]}
                audio_bytes = base64.b64decode(audio_b64)
                provider_name = config.get("provider", "openai_whisper")
                language = config.get("language") or None
                if provider_name == "openai_whisper":
                    try:
                        from agentforge.speech.openai_whisper import LocalWhisperASR
                        provider = LocalWhisperASR()
                        transcript = await provider.transcribe(audio_bytes, language=language)
                    except ImportError:
                        transcript = "[asr] openai package not installed. pip install openai"
                else:
                    transcript = f"[asr] provider '{provider_name}' not supported locally."
                return {"messages": [HumanMessage(content=transcript)], "audio_b64": None}

            elif node_type == "tts":
                import base64
                last_ai = next(
                    (m for m in reversed(messages) if isinstance(m, AIMessage)), None
                )
                text = str(last_ai.content) if last_ai else ""
                provider_name = config.get("provider", "openai_tts")
                voice = config.get("voice", "nova")
                if provider_name == "openai_tts":
                    try:
                        from agentforge.speech.openai_tts import LocalOpenAITTS
                        provider = LocalOpenAITTS()
                        mp3_bytes = await provider.synthesize(text, voice=voice)
                        return {"audio_b64": base64.b64encode(mp3_bytes).decode()}
                    except ImportError:
                        return {"messages": [AIMessage(content="[tts] openai package not installed.")]}
                return {"messages": [AIMessage(content=f"[tts] provider '{provider_name}' not supported locally.")]}
```

Also add `HumanMessage` to imports at the top of `agent.py` if not already there:
```python
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
```
(It's already imported — no change needed.)

- [ ] **Step 6: Run full SDK suite to check no regressions**

```bash
cd sdk && uv run --with pytest pytest tests/unit/ -v
```
Expected: all previous 77 + 6 new = 83 passed

- [ ] **Step 7: Commit**

```bash
git add sdk/src/agentforge/builder.py sdk/src/agentforge/agent.py sdk/tests/unit/test_speech_builder.py
git commit -m "feat(sdk): add asr_node() and tts_node() builder methods + local ASR/TTS execution"
```

---

## Task 8: Run full backend test suite

**Files:** No new files — validation only.

- [ ] **Step 1: Run all speech tests**

```bash
cd backend && uv run --with pytest pytest tests/test_speech.py -v
```
Expected: all 12 speech tests pass

- [ ] **Step 2: Run full backend suite**

```bash
cd backend && uv run --with pytest pytest tests/ -q --ignore=tests/infrastructure -x
```
Expected: no regressions (coverage may decrease slightly for new files — acceptable)

- [ ] **Step 3: Commit if any fixes were needed**

```bash
git add -A
git commit -m "fix(speech): address test suite regressions"
```

---

## Task 9: Frontend — ASR/TTS nodes in builder

**Files:**
- Modify: `frontend/src/app/agents/[id]/builder/page.tsx`

The builder has a `NodeKind` union type and a `CustomNode` component with `if nodeType === "xxx"` config panels, plus a palette array.

- [ ] **Step 1: Extend `NodeKind` type**

In `builder/page.tsx`, find:
```typescript
type NodeKind = "llm" | "tool" | "subagent" | "conditional" | "interrupt";
```
Replace with:
```typescript
type NodeKind = "llm" | "tool" | "subagent" | "conditional" | "interrupt" | "asr" | "tts";
```

- [ ] **Step 2: Add ASR config panel in `CustomNode`**

In `CustomNode`, after the `{nodeType === "interrupt" && ...}` block, add:
```tsx
      {nodeType === "asr" && (
        <div className="space-y-2">
          <label className="text-[10px] uppercase text-af-muted-dim">Provider</label>
          <select
            value={(config?.provider as string) || "openai_whisper"}
            onChange={(e) => updateConfig("provider", e.target.value)}
            className="af-input nodrag p-2 text-xs"
          >
            <option value="openai_whisper">OpenAI Whisper</option>
          </select>
          <label className="text-[10px] uppercase text-af-muted-dim">Language (optional)</label>
          <input
            value={(config?.language as string) || ""}
            onChange={(e) => updateConfig("language", e.target.value)}
            placeholder="e.g. fr, en"
            className="af-input nodrag p-2 text-xs"
          />
        </div>
      )}
      {nodeType === "tts" && (
        <div className="space-y-2">
          <label className="text-[10px] uppercase text-af-muted-dim">Provider</label>
          <select
            value={(config?.provider as string) || "openai_tts"}
            onChange={(e) => updateConfig("provider", e.target.value)}
            className="af-input nodrag p-2 text-xs"
          >
            <option value="openai_tts">OpenAI TTS</option>
            <option value="elevenlabs">ElevenLabs</option>
          </select>
          <label className="text-[10px] uppercase text-af-muted-dim">Voice</label>
          <select
            value={(config?.voice as string) || "nova"}
            onChange={(e) => updateConfig("voice", e.target.value)}
            className="af-input nodrag p-2 text-xs"
          >
            {["alloy", "echo", "fable", "onyx", "nova", "shimmer"].map((v) => (
              <option key={v} value={v}>{v}</option>
            ))}
          </select>
        </div>
      )}
```

- [ ] **Step 3: Add ASR/TTS buttons to the palette**

Find the palette array:
```typescript
          [
            ["llm", "LLM"],
            ["tool", "Tool"],
            ["subagent", "Subagent"],
            ["conditional", "Router"],
            ["interrupt", "Interrupt (HITL)"],
          ] as const
```
Replace with:
```typescript
          [
            ["llm", "LLM"],
            ["tool", "Tool"],
            ["subagent", "Subagent"],
            ["conditional", "Router"],
            ["interrupt", "Interrupt (HITL)"],
            ["asr", "ASR (Mic)"],
            ["tts", "TTS (Speaker)"],
          ] as const
```

- [ ] **Step 4: Add default config for new node types in `addPaletteNode`**

Find the `addPaletteNode` function (it creates a new node with default config). Locate where it initializes `config` based on `nodeType` and add:
```typescript
    const defaultConfig: Record<string, string> =
      k === "llm" ? { prompt: "" }
      : k === "tool" ? { tool_name: "" }
      : k === "subagent" ? { subagent_id: "" }
      : k === "asr" ? { provider: "openai_whisper", language: "" }
      : k === "tts" ? { provider: "openai_tts", voice: "nova" }
      : {};
```
Update the node creation to use `defaultConfig` instead of `{}` for config.

- [ ] **Step 5: Typecheck**

```bash
cd frontend && npm run typecheck 2>&1 | grep -i error | head -20
```
Expected: 0 errors related to the new node types.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/app/agents/\[id\]/builder/page.tsx
git commit -m "feat(frontend): add ASR/TTS node types to visual builder"
```

---

## Task 10: Frontend — ExecutionLog audio player + VoiceTestButton

**Files:**
- Modify: `frontend/src/components/execution/ExecutionLog.tsx`
- Modify or locate: `frontend/src/app/agents/[id]/page.tsx`

- [ ] **Step 1: Update ExecutionLog to render audio events**

The current `LogLine` type is `{ event: string; data: string; at: number }`. When `event === "audio"`, parse `data` as JSON and render an `<audio>` player.

Replace `frontend/src/components/execution/ExecutionLog.tsx` with:
```tsx
"use client";

type LogLine = { event: string; data: string; at: number };

function AudioPlayer({ dataJson }: { dataJson: string }) {
  try {
    const { audio_b64 } = JSON.parse(dataJson) as { audio_b64: string };
    const src = `data:audio/mp3;base64,${audio_b64}`;
    return (
      <audio
        controls
        src={src}
        className="mt-1 h-8 w-full"
      />
    );
  } catch {
    return <span className="text-af-error">invalid audio data</span>;
  }
}

export function ExecutionLog({ lines }: { lines: LogLine[] }) {
  if (lines.length === 0) return null;
  return (
    <div className="af-card border-af-border/80 bg-af-surface-void/50 p-4 font-mono text-xs text-af-on-surface">
      <p className="mb-2 text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
        Execution stream
      </p>
      <ul className="max-h-64 space-y-1 overflow-y-auto">
        {lines.map((l, i) => (
          <li key={`${l.at}-${i}`} className="break-all">
            <span className="text-af-tertiary">{l.event}</span>
            <span className="text-af-muted-dim"> · </span>
            {l.event === "audio" ? (
              <AudioPlayer dataJson={l.data} />
            ) : (
              <span className="text-af-muted">{l.data}</span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
```

- [ ] **Step 2: Add VoiceTestButton to agent detail page**

First, read the agent detail page to understand its structure:
```bash
head -80 frontend/src/app/agents/\[id\]/page.tsx
```

Then add a `VoiceTestButton` component inline. It:
1. Shows a "🎤 Test vocal" button
2. On click, uses `navigator.mediaDevices.getUserMedia` to record audio
3. Sends audio to `POST /api/v1/agents/{id}/execute/audio` as multipart
4. Streams SSE response, adds lines to a local log
5. Plays back audio if `audio` event is received

Add to the agent detail page (find where execution buttons are rendered):

```tsx
function VoiceTestButton({ agentId }: { agentId: string }) {
  const [recording, setRecording] = useState(false);
  const [log, setLog] = useState<{ event: string; data: string; at: number }[]>([]);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const start = async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const recorder = new MediaRecorder(stream);
    recorderRef.current = recorder;
    chunksRef.current = [];
    recorder.ondataavailable = (e) => chunksRef.current.push(e.data);
    recorder.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop());
      const blob = new Blob(chunksRef.current, { type: "audio/webm" });
      const form = new FormData();
      form.append("file", blob, "recording.webm");
      const resp = await fetch(`/api/v1/agents/${agentId}/execute/audio`, {
        method: "POST",
        headers: { Authorization: `Bearer ${localStorage.getItem("token") ?? ""}` },
        body: form,
      });
      const reader = resp.body!.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const parts = buf.split("\n\n");
        buf = parts.pop() ?? "";
        for (const part of parts) {
          const eventLine = part.match(/^event: (.+)$/m)?.[1] ?? "message";
          const dataLine = part.match(/^data: (.+)$/m)?.[1] ?? "";
          setLog((prev) => [...prev, { event: eventLine, data: dataLine, at: Date.now() }]);
        }
      }
    };
    recorder.start();
    setRecording(true);
  };

  const stop = () => {
    recorderRef.current?.stop();
    setRecording(false);
  };

  return (
    <div className="space-y-2">
      <button
        type="button"
        onClick={recording ? stop : start}
        className={`rounded-lg border px-3 py-1.5 text-xs font-bold transition-colors ${
          recording
            ? "border-red-500 text-red-400 hover:bg-red-500/10"
            : "border-af-border text-af-on-surface hover:border-af-primary hover:text-af-primary"
        }`}
      >
        {recording ? "⏹ Stop & Send" : "🎤 Test vocal"}
      </button>
      {log.length > 0 && <ExecutionLog lines={log} />}
    </div>
  );
}
```

Add the required imports at the top of `page.tsx`:
```tsx
import { useRef } from "react";
import { ExecutionLog } from "@/components/execution/ExecutionLog";
```

Render `<VoiceTestButton agentId={id} />` near the existing execute button.

- [ ] **Step 3: Typecheck**

```bash
cd frontend && npm run typecheck 2>&1 | grep -i error | head -20
```
Expected: 0 errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/execution/ExecutionLog.tsx frontend/src/app/agents/\[id\]/page.tsx
git commit -m "feat(frontend): add audio playback in ExecutionLog + VoiceTestButton"
```

---

## Task 11: Final validation

- [ ] **Step 1: Run SDK Python suite**

```bash
cd sdk && uv run --with pytest pytest tests/unit/ -q
```
Expected: 83 passed (77 original + 6 speech builder)

- [ ] **Step 2: Run SDK TypeScript suite**

```bash
cd sdk-js && npm test
```
Expected: 42 passed

- [ ] **Step 3: Run backend speech tests**

```bash
cd backend && uv run --with pytest pytest tests/test_speech.py -v
```
Expected: 12 passed

- [ ] **Step 4: Frontend typecheck**

```bash
cd frontend && npm run typecheck
```
Expected: 0 errors

- [ ] **Step 5: Commit final**

```bash
git commit --allow-empty -m "chore: Phase N3 complete — speech ASR/TTS nodes"
```

---

## Self-review

**Spec coverage check:**
- ✅ `asr` node type: Task 5 + 7
- ✅ `tts` node type: Task 5 + 7
- ✅ `openai_whisper` provider: Task 2
- ✅ `openai_tts` provider: Task 3
- ✅ `elevenlabs` provider: Task 4
- ✅ `audio_b64` in AgentState: Task 5
- ✅ `POST /execute/audio` multipart endpoint: Task 6
- ✅ SDK `asr_node()` / `tts_node()`: Task 7
- ✅ React Flow palette + config panels: Task 9
- ✅ ExecutionLog `<audio>` player: Task 10
- ✅ VoiceTestButton on agent detail: Task 10

**Type consistency:** `NodeKind` extended consistently in Task 9. `_State.audio_b64: str | None` used consistently in Tasks 5, 6. `asr_node` / `tts_node` return `"AgentBuilder"` like all other builder methods.

**Note for Task 5 (threading `settings` into `_run_asr_node`):** The function `_build_node_step` in `langgraph_orchestrator.py` receives `settings: Settings` as a parameter — pass it through to `_run_asr_node` / `_run_tts_node` the same way.
