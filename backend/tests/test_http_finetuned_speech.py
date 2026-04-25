"""Unit tests for HTTP fine-tuned speech providers (Modal-compatible endpoints)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.infrastructure.speech.providers.http_finetuned_asr import HttpFinetunedASR
from app.infrastructure.speech.providers.http_finetuned_tts import HttpFinetunedTTS


class _FakeResponse:
    def __init__(
        self,
        *,
        json_data=None,
        text: str = "",
        content: bytes = b"",
        ctype: str = "",
    ) -> None:
        self.status_code = 200
        self.headers = {"content-type": ctype}
        self._json = json_data
        self.text = text
        self.content = content

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._json


class _FakeAsyncClient:
    def __init__(self, response: _FakeResponse) -> None:
        self._response = response
        self.post = AsyncMock(return_value=self._response)

    async def __aenter__(self) -> _FakeAsyncClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None


@pytest.mark.asyncio
async def test_http_finetuned_asr_json_text_key() -> None:
    resp = _FakeResponse(json_data={"text": "hello world"}, ctype="application/json")
    fake = _FakeAsyncClient(resp)
    patch_path = "app.infrastructure.speech.providers.http_finetuned_asr.httpx.AsyncClient"
    with patch(patch_path, return_value=fake):
        asr = HttpFinetunedASR("https://api.example/transcribe")
        out = await asr.transcribe(b"\x00\x01", filename="a.webm")
    assert out == "hello world"
    fake.post.assert_called_once()


@pytest.mark.asyncio
async def test_http_finetuned_tts_raw_mp3() -> None:
    mp3 = b"\xff\xfb\x90\x00"
    resp = _FakeResponse(content=mp3, ctype="audio/mpeg")
    fake = _FakeAsyncClient(resp)
    patch_path = "app.infrastructure.speech.providers.http_finetuned_tts.httpx.AsyncClient"
    with patch(patch_path, return_value=fake):
        tts = HttpFinetunedTTS("https://api.example/speak", voice_id="v1")
        out = await tts.synthesize("hi there")
    assert out == mp3
    call_kw = fake.post.call_args.kwargs
    assert call_kw["json"]["text"] == "hi there"
    assert call_kw["json"]["voice_id"] == "v1"


@pytest.mark.asyncio
async def test_http_finetuned_tts_audio_b64() -> None:
    import base64

    raw = b"fake-mp3"
    resp = _FakeResponse(
        json_data={"audio_b64": base64.b64encode(raw).decode()},
        ctype="application/json",
    )
    fake = _FakeAsyncClient(resp)
    patch_path = "app.infrastructure.speech.providers.http_finetuned_tts.httpx.AsyncClient"
    with patch(patch_path, return_value=fake):
        tts = HttpFinetunedTTS("https://api.example/speak")
        out = await tts.synthesize("x", voice="alloy")
    assert out == raw
