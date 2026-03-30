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
