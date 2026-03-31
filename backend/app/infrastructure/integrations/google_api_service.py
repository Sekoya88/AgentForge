"""Google Gmail + Calendar API (user OAuth access token)."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.mime.text import MIMEText

import httpx


@dataclass
class EmailSummary:
    id: str
    from_: str
    subject: str
    date: str
    snippet: str


@dataclass
class CalendarEvent:
    id: str
    title: str
    start: str
    end: str
    location: str | None
    attendees: list[str]


class GoogleApiService:
    GMAIL_BASE = "https://gmail.googleapis.com/gmail/v1"
    CALENDAR_BASE = "https://www.googleapis.com/calendar/v3"

    def __init__(self, access_token: str) -> None:
        self._headers = {"Authorization": f"Bearer {access_token}"}

    async def list_emails(
        self,
        max_results: int = 10,
        query: str = "in:inbox",
        *,
        client: httpx.AsyncClient | None = None,
    ) -> list[EmailSummary]:
        own = client is None
        c = client or httpx.AsyncClient(timeout=30.0)
        try:
            resp = await c.get(
                f"{self.GMAIL_BASE}/users/me/messages",
                headers=self._headers,
                params={"maxResults": max_results, "q": query},
            )
            resp.raise_for_status()
            messages = resp.json().get("messages") or []
            results: list[EmailSummary] = []
            for msg in messages:
                mid = msg.get("id")
                if not mid:
                    continue
                detail = await c.get(
                    f"{self.GMAIL_BASE}/users/me/messages/{mid}",
                    headers=self._headers,
                    params={
                        "format": "metadata",
                        "metadataHeaders": ["From", "Subject", "Date"],
                    },
                )
                detail.raise_for_status()
                d = detail.json()
                hdr_list = d.get("payload", {}).get("headers") or []
                hdrs = {h["name"]: h["value"] for h in hdr_list if "name" in h and "value" in h}
                results.append(
                    EmailSummary(
                        id=str(mid),
                        from_=hdrs.get("From", ""),
                        subject=hdrs.get("Subject", ""),
                        date=hdrs.get("Date", ""),
                        snippet=str(d.get("snippet") or ""),
                    )
                )
            return results
        finally:
            if own:
                await c.aclose()

    async def send_email(self, to: str, subject: str, body: str) -> str:
        msg = MIMEText(body)
        msg["to"] = to
        msg["subject"] = subject
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        async with httpx.AsyncClient(timeout=30.0) as c:
            resp = await c.post(
                f"{self.GMAIL_BASE}/users/me/messages/send",
                headers=self._headers,
                json={"raw": raw},
            )
            resp.raise_for_status()
            return str(resp.json().get("id", ""))

    async def list_events(self, days_ahead: int = 7) -> list[CalendarEvent]:
        time_min = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        time_max = (
            (datetime.now(UTC) + timedelta(days=days_ahead)).isoformat().replace("+00:00", "Z")
        )
        async with httpx.AsyncClient(timeout=30.0) as c:
            resp = await c.get(
                f"{self.CALENDAR_BASE}/calendars/primary/events",
                headers=self._headers,
                params={
                    "timeMin": time_min,
                    "timeMax": time_max,
                    "maxResults": 20,
                    "singleEvents": True,
                    "orderBy": "startTime",
                },
            )
            resp.raise_for_status()
            items = resp.json().get("items") or []
            out: list[CalendarEvent] = []
            for e in items:
                st = e.get("start") or {}
                en = e.get("end") or {}
                out.append(
                    CalendarEvent(
                        id=str(e.get("id", "")),
                        title=str(e.get("summary") or "Untitled"),
                        start=str(st.get("dateTime") or st.get("date") or ""),
                        end=str(en.get("dateTime") or en.get("date") or ""),
                        location=e.get("location"),
                        attendees=[a["email"] for a in (e.get("attendees") or []) if "email" in a],
                    )
                )
            return out

    async def create_event(
        self,
        title: str,
        start: str,
        end: str,
        *,
        location: str | None = None,
        attendees: list[str] | None = None,
    ) -> str:
        body: dict = {
            "summary": title,
            "start": {"dateTime": start, "timeZone": "UTC"},
            "end": {"dateTime": end, "timeZone": "UTC"},
        }
        if location:
            body["location"] = location
        if attendees:
            body["attendees"] = [{"email": a} for a in attendees]
        async with httpx.AsyncClient(timeout=30.0) as c:
            resp = await c.post(
                f"{self.CALENDAR_BASE}/calendars/primary/events",
                headers=self._headers,
                json=body,
            )
            resp.raise_for_status()
            return str(resp.json().get("id", ""))


def emails_to_json(emails: list[EmailSummary]) -> str:
    return json.dumps(
        [
            {
                "id": e.id,
                "from": e.from_,
                "subject": e.subject,
                "date": e.date,
                "snippet": e.snippet[:500],
            }
            for e in emails
        ],
        indent=2,
    )


def events_to_json(events: list[CalendarEvent]) -> str:
    return json.dumps(
        [
            {
                "id": e.id,
                "title": e.title,
                "start": e.start,
                "end": e.end,
                "location": e.location,
                "attendees": e.attendees,
            }
            for e in events
        ],
        indent=2,
    )
