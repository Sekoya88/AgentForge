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
