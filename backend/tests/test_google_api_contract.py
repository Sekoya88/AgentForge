"""Contract tests for GoogleApiService — verifies API call shapes without hitting real APIs.

All HTTP traffic is intercepted via httpx.MockTransport injected through unittest.mock.patch
so no real Google credentials are needed.
"""

from __future__ import annotations

import base64
import json
from email import message_from_bytes
from unittest.mock import patch

import httpx
import pytest

from app.infrastructure.integrations.google_api_service import GoogleApiService

pytestmark = pytest.mark.asyncio

_ACCESS_TOKEN = "fake-access-token"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _CapturingTransport(httpx.AsyncBaseTransport):
    """Records every request and returns a pre-configured response."""

    def __init__(self, response_json: dict) -> None:
        self._response_json = response_json
        self.requests: list[httpx.Request] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(200, json=self._response_json)

    @property
    def last(self) -> httpx.Request:
        return self.requests[-1]


def _make_patched_client_class(transport: _CapturingTransport):
    """Return an httpx.AsyncClient subclass that always uses *transport*."""

    class _PatchedClient(httpx.AsyncClient):
        def __init__(self, **kwargs):  # type: ignore[override]
            kwargs["transport"] = transport
            super().__init__(**kwargs)

    return _PatchedClient


# ---------------------------------------------------------------------------
# create_event (Calendar)
# ---------------------------------------------------------------------------


async def test_create_event_sends_expected_json_schema() -> None:
    """create_event must POST a body with summary, start, and end keys."""
    transport = _CapturingTransport({"id": "evt-abc123"})

    with patch("httpx.AsyncClient", _make_patched_client_class(transport)):
        svc = GoogleApiService(_ACCESS_TOKEN)
        event_id = await svc.create_event(
            "Team Sync",
            "2026-04-02T10:00:00Z",
            "2026-04-02T11:00:00Z",
        )

    assert event_id == "evt-abc123"

    req = transport.last
    assert "calendar/v3/calendars/primary/events" in str(req.url)
    assert req.method == "POST"
    assert req.headers.get("authorization") == f"Bearer {_ACCESS_TOKEN}"

    body = json.loads(req.content)
    assert "summary" in body, "event body must have 'summary' key"
    assert "start" in body, "event body must have 'start' key"
    assert "end" in body, "event body must have 'end' key"
    assert body["summary"] == "Team Sync"
    assert body["start"]["dateTime"] == "2026-04-02T10:00:00Z"
    assert body["end"]["dateTime"] == "2026-04-02T11:00:00Z"


async def test_create_event_includes_optional_location_and_attendees() -> None:
    """Optional location and attendees are serialised into the event body correctly."""
    transport = _CapturingTransport({"id": "evt-xyz"})

    with patch("httpx.AsyncClient", _make_patched_client_class(transport)):
        svc = GoogleApiService(_ACCESS_TOKEN)
        await svc.create_event(
            "Interview",
            "2026-04-03T14:00:00Z",
            "2026-04-03T15:00:00Z",
            location="Room 42",
            attendees=["alice@example.com", "bob@example.com"],
        )

    body = json.loads(transport.last.content)
    assert body.get("location") == "Room 42"
    attendee_emails = [a["email"] for a in body.get("attendees", [])]
    assert "alice@example.com" in attendee_emails
    assert "bob@example.com" in attendee_emails


async def test_create_event_omits_optional_fields_when_not_provided() -> None:
    """location and attendees keys must be absent when not supplied."""
    transport = _CapturingTransport({"id": "evt-min"})

    with patch("httpx.AsyncClient", _make_patched_client_class(transport)):
        svc = GoogleApiService(_ACCESS_TOKEN)
        await svc.create_event("Standup", "2026-04-04T09:00:00Z", "2026-04-04T09:30:00Z")

    body = json.loads(transport.last.content)
    assert "location" not in body
    assert "attendees" not in body


# ---------------------------------------------------------------------------
# send_email (Gmail)
# ---------------------------------------------------------------------------


async def test_send_email_posts_raw_mime_to_gmail_send() -> None:
    """send_email must POST to the Gmail send endpoint with a valid raw MIME payload."""
    transport = _CapturingTransport({"id": "msg-999"})

    with patch("httpx.AsyncClient", _make_patched_client_class(transport)):
        svc = GoogleApiService(_ACCESS_TOKEN)
        msg_id = await svc.send_email(
            to="recipient@example.com",
            subject="Hello from test",
            body="This is the body.",
        )

    assert msg_id == "msg-999"

    req = transport.last
    assert "gmail" in str(req.url)
    assert "messages/send" in str(req.url)
    assert req.method == "POST"
    assert req.headers.get("authorization") == f"Bearer {_ACCESS_TOKEN}"

    payload = json.loads(req.content)
    assert "raw" in payload, "Gmail send payload must contain 'raw' key"

    # Decode and parse the MIME message to verify header shape
    raw_bytes = base64.urlsafe_b64decode(payload["raw"] + "==")
    mime_msg = message_from_bytes(raw_bytes)
    assert mime_msg["to"] == "recipient@example.com"
    assert mime_msg["subject"] == "Hello from test"


# ---------------------------------------------------------------------------
# list_emails (Gmail) — shape of query parameters
# ---------------------------------------------------------------------------


async def test_list_emails_queries_correct_endpoint_and_params() -> None:
    """list_emails must call the Gmail messages list endpoint with maxResults and q params."""
    # list_emails accepts an optional client kwarg — inject directly
    call_count = 0

    def handler(req: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        # First call: list endpoint returns empty list → no detail fetches needed
        return httpx.Response(200, json={"messages": []})

    capture: list[httpx.Request] = []

    class _RecordingTransport(httpx.MockTransport):
        async def handle_async_request(self, req: httpx.Request) -> httpx.Response:
            capture.append(req)
            return await super().handle_async_request(req)

    rec_transport = _RecordingTransport(handler)

    async with httpx.AsyncClient(transport=rec_transport) as client:
        svc = GoogleApiService(_ACCESS_TOKEN)
        emails = await svc.list_emails(max_results=5, query="is:unread", client=client)

    assert emails == []
    assert len(capture) >= 1

    list_req = capture[0]
    assert "gmail" in str(list_req.url)
    assert list_req.url.params.get("maxResults") == "5"
    assert list_req.url.params.get("q") == "is:unread"
    assert list_req.headers.get("authorization") == f"Bearer {_ACCESS_TOKEN}"
