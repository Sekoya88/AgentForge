"""Google OAuth 2.0 authorization code + PKCE (S256)."""

from __future__ import annotations

import base64
import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx
from jose import JWTError, jwt

from app.config import Settings

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
STATE_TYP = "google_oauth_state"
# Space-separated; includes Gmail + Calendar for agent tools (users must re-consent if upgrading).
GOOGLE_OAUTH_SCOPES = (
    "openid "
    "https://www.googleapis.com/auth/userinfo.email "
    "https://www.googleapis.com/auth/userinfo.profile "
    "https://www.googleapis.com/auth/gmail.readonly "
    "https://www.googleapis.com/auth/gmail.send "
    "https://www.googleapis.com/auth/calendar.readonly "
    "https://www.googleapis.com/auth/calendar.events"
)
SCOPE_GMAIL_READONLY = "https://www.googleapis.com/auth/gmail.readonly"
SCOPE_GMAIL_SEND = "https://www.googleapis.com/auth/gmail.send"
SCOPE_CALENDAR_READONLY = "https://www.googleapis.com/auth/calendar.readonly"
SCOPE_CALENDAR_EVENTS = "https://www.googleapis.com/auth/calendar.events"


def generate_pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    challenge_bytes = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(challenge_bytes).rstrip(b"=").decode("ascii")
    return verifier, challenge


def encode_oauth_state(settings: Settings, code_verifier: str) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=10)
    return jwt.encode(
        {"cv": code_verifier, "exp": expire, "typ": STATE_TYP},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_oauth_state(settings: Settings, state: str) -> str:
    try:
        payload = jwt.decode(
            state,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as e:
        raise ValueError("invalid OAuth state") from e
    if payload.get("typ") != STATE_TYP:
        raise ValueError("invalid OAuth state type")
    cv = payload.get("cv")
    if not isinstance(cv, str) or not cv:
        raise ValueError("invalid OAuth state payload")
    return cv


def build_authorize_url(settings: Settings) -> str:
    if not settings.google_oauth_client_id or not settings.google_oauth_redirect_uri:
        raise RuntimeError("Google OAuth is not configured")
    verifier, challenge = generate_pkce_pair()
    state = encode_oauth_state(settings, verifier)
    q = urlencode(
        {
            "client_id": settings.google_oauth_client_id,
            "redirect_uri": settings.google_oauth_redirect_uri,
            "response_type": "code",
            "scope": GOOGLE_OAUTH_SCOPES,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "access_type": "offline",
            "prompt": "consent",
        }
    )
    return f"{GOOGLE_AUTH_URL}?{q}"


async def exchange_code_for_tokens(
    settings: Settings,
    code: str,
    code_verifier: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    if not settings.google_oauth_client_secret:
        raise RuntimeError("Google OAuth client secret is not configured")
    data = {
        "code": code,
        "client_id": settings.google_oauth_client_id,
        "client_secret": settings.google_oauth_client_secret,
        "redirect_uri": settings.google_oauth_redirect_uri,
        "grant_type": "authorization_code",
        "code_verifier": code_verifier,
    }
    own_client = client is None
    c = client or httpx.AsyncClient(timeout=30.0)
    try:
        r = await c.post(GOOGLE_TOKEN_URL, data=data)
        r.raise_for_status()
        return r.json()
    finally:
        if own_client:
            await c.aclose()


async def refresh_access_token_with_refresh(
    settings: Settings,
    refresh_token: str,
    *,
    client: httpx.AsyncClient,
) -> dict[str, Any]:
    if not settings.google_oauth_client_secret:
        raise RuntimeError("Google OAuth client secret is not configured")
    data = {
        "client_id": settings.google_oauth_client_id,
        "client_secret": settings.google_oauth_client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    r = await client.post(GOOGLE_TOKEN_URL, data=data)
    r.raise_for_status()
    return r.json()


async def fetch_google_userinfo(
    access_token: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    own_client = client is None
    c = client or httpx.AsyncClient(timeout=30.0)
    try:
        r = await c.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        r.raise_for_status()
        return r.json()
    finally:
        if own_client:
            await c.aclose()
