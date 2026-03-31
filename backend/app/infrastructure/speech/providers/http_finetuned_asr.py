"""ASR via HTTP endpoint (e.g. Modal web endpoint for fine-tuned Whisper)."""

from __future__ import annotations

import httpx


class HttpFinetunedASR:
    """POST multipart audio to ``endpoint_url``.

    Response: JSON with ``text`` / ``transcript``, or plain text body.
    """

    def __init__(
        self,
        endpoint_url: str,
        headers: dict[str, str] | None = None,
        timeout_s: float = 120.0,
    ) -> None:
        self._url = endpoint_url.rstrip("/")
        self._headers = dict(headers or {})
        self._timeout = timeout_s

    async def transcribe(
        self,
        audio_bytes: bytes,
        language: str | None = None,
        filename: str = "audio.webm",
    ) -> str:
        files = {"file": (filename, audio_bytes)}
        data: dict[str, str] = {}
        if language:
            data["language"] = language
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            r = await client.post(self._url, files=files, data=data, headers=self._headers)
        r.raise_for_status()
        ct = (r.headers.get("content-type") or "").lower()
        if "application/json" in ct:
            payload = r.json()
            if isinstance(payload, dict):
                return str(
                    payload.get("text") or payload.get("transcript") or payload.get("message") or ""
                )
            return str(payload)
        return r.text.strip()
