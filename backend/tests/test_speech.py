"""Tests for speech providers and orchestrator nodes."""

from unittest.mock import AsyncMock, MagicMock

import pytest


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
