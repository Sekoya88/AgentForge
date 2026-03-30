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
