"""Tests for speech providers and orchestrator nodes."""


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
