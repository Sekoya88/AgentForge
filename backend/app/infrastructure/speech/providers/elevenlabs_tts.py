from typing import Any


class ElevenLabsTTS:
    """TTS provider using ElevenLabs API."""

    def __init__(self, client: Any = None, api_key: str | None = None) -> None:
        if client is not None:
            self._client = client
        else:
            from elevenlabs.client import AsyncElevenLabs

            self._client = AsyncElevenLabs(api_key=api_key)

    async def synthesize(self, text: str, voice: str = "nova") -> bytes:
        # Note: mapping 'nova' to a default ElevenLabs voice if desired,
        # or using it as the Voice ID directly.
        # Let's assume voice passed here is the ElevenLabs Voice ID (e.g., 'JBFqnCBsd6RMkjVDRZzb').
        # If the user passed an OpenAI name like 'nova', they'll need to map it in their logic.

        audio_stream = await self._client.generate(
            text=text,
            voice=voice,
            model="eleven_multilingual_v2",
        )

        audio_bytes = b""
        async for chunk in audio_stream:
            if chunk:
                audio_bytes += chunk

        return audio_bytes
