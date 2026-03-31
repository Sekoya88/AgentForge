"""TTS via HTTP (e.g. Modal); mirrors backend contract."""

from __future__ import annotations

import base64

import httpx


class LocalHttpFinetunedTTS:
    """POST JSON ``text`` + ``voice_id``; MP3 body or JSON ``audio_b64``."""

    def __init__(
        self,
        endpoint_url: str,
        voice_id: str | None = None,
        headers: dict[str, str] | None = None,
        timeout_s: float = 120.0,
    ) -> None:
        self._url = endpoint_url.rstrip("/")
        self._voice_id = voice_id
        self._headers = dict(headers or {})
        self._timeout = timeout_s

    async def synthesize(self, text: str, voice: str = "nova") -> bytes:
        vid = self._voice_id or voice
        payload: dict[str, str] = {"text": text, "voice": vid, "voice_id": vid}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            r = await client.post(self._url, json=payload, headers=self._headers)
        r.raise_for_status()
        ct = (r.headers.get("content-type") or "").lower()
        if "application/json" in ct:
            data = r.json()
            if isinstance(data, dict):
                b64 = data.get("audio_b64")
                if isinstance(b64, str) and b64.strip():
                    return base64.b64decode(b64)
        return r.content
