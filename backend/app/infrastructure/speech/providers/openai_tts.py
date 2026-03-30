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
