"""Tests for speech providers and orchestrator nodes."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage


def test_ports_import():
    from app.infrastructure.speech.ports import ASRProvider, TTSProvider

    assert ASRProvider is not None
    assert TTSProvider is not None


def test_asr_provider_is_protocol():

    from app.infrastructure.speech.ports import ASRProvider

    assert hasattr(ASRProvider, "__protocol_attrs__") or hasattr(ASRProvider, "transcribe")


def test_tts_provider_is_protocol():
    from app.infrastructure.speech.ports import TTSProvider

    assert hasattr(TTSProvider, "synthesize")


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
    mock_client.audio.transcriptions.create = AsyncMock(return_value=MagicMock(text="Hello"))
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


@pytest.mark.asyncio
async def test_elevenlabs_tts_synthesizes():
    from app.infrastructure.speech.providers.elevenlabs_tts import ElevenLabsTTS

    async def fake_audio_stream():
        yield b"ID3"
        yield b"chunk"

    mock_client = MagicMock()
    mock_client.generate = AsyncMock(return_value=fake_audio_stream())

    provider = ElevenLabsTTS(client=mock_client)
    result = await provider.synthesize("Hello", voice="eleven_id")

    assert result == b"ID3chunk"
    call_kwargs = mock_client.generate.call_args.kwargs
    assert call_kwargs.get("text") == "Hello"
    assert call_kwargs.get("voice") == "eleven_id"


@pytest.mark.asyncio
async def test_asr_node_transcribes_and_injects_message():
    import base64

    from app.config import Settings
    from app.infrastructure.orchestration.langgraph_orchestrator import _run_asr_node

    fake_audio = base64.b64encode(b"fakeaudio").decode()
    settings = MagicMock(spec=Settings)
    settings.openai_api_key = "sk-test"

    with patch("app.infrastructure.orchestration.node_builders._build_asr_provider") as mock_build:
        mock_provider = MagicMock()
        mock_provider.transcribe = AsyncMock(return_value="hello world")
        mock_build.return_value = mock_provider

        result = await _run_asr_node(
            {"messages": [], "audio_b64": fake_audio},
            {"provider": "openai_whisper", "language": "en"},
            settings,
            openai_key=None,
        )
    assert len(result["messages"]) == 1
    assert isinstance(result["messages"][0], HumanMessage)
    assert "hello world" in str(result["messages"][0].content)


@pytest.mark.asyncio
async def test_tts_node_synthesizes_last_ai_message():
    import base64

    from app.config import Settings
    from app.infrastructure.orchestration.langgraph_orchestrator import _run_tts_node

    fake_mp3 = b"MP3DATA"
    settings = MagicMock(spec=Settings)
    settings.openai_api_key = "sk-test"
    settings.elevenlabs_api_key = None

    with patch("app.infrastructure.orchestration.node_builders._build_tts_provider") as mock_build:
        mock_provider = MagicMock()
        mock_provider.synthesize = AsyncMock(return_value=fake_mp3)
        mock_build.return_value = mock_provider

        result = await _run_tts_node(
            {"messages": [AIMessage(content="Hello!")], "audio_b64": None},
            {"provider": "openai_tts", "voice": "nova"},
            settings,
            openai_key=None,
        )

    assert "audio_b64" in result
    decoded = base64.b64decode(result["audio_b64"])
    assert decoded == fake_mp3


@pytest.mark.usefixtures("alembic_ready")
@pytest.mark.asyncio
async def test_execute_audio_endpoint_requires_file(client):
    email = f"sp_{uuid.uuid4().hex[:8]}@example.com"
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "longpassword1", "display_name": "S"},
    )
    assert r.status_code == 200, r.text
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "longpassword1"},
    )
    assert r.status_code == 200, r.text
    access = r.json()["access_token"]
    resp = await client.post(
        "/api/v1/agents/00000000-0000-0000-0000-000000000001/execute/audio",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert resp.status_code == 422
