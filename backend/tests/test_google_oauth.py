"""Google OAuth service: HTTP mocked via httpx.MockTransport."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import httpx
import pytest

from app.application.services.google_oauth_service import GoogleOAuthService
from app.config import Settings
from app.domain.entities.user import User
from app.infrastructure.auth.google_oauth_flow import (
    build_authorize_url,
    encode_oauth_state,
    generate_pkce_pair,
)


class _FakeUsers:
    def __init__(self) -> None:
        self.created: list[tuple[str, str | None]] = []

    async def get_by_email(self, email: str) -> User | None:
        return None

    async def create_oauth_user(self, email: str, display_name: str | None) -> User:
        self.created.append((email, display_name))
        now = datetime.now(UTC)
        return User(
            id=uuid4(),
            email=email,
            display_name=display_name,
            collect_speech_examples=False,
            created_at=now,
            updated_at=now,
        )


class _FakeSocial:
    def __init__(self) -> None:
        self.calls: list[tuple[UUID, str, str | None]] = []

    async def upsert_google(
        self,
        user_id: UUID,
        provider_id: str,
        email: str | None,
        access_token_cipher: str | None,
        refresh_token_cipher: str | None,
        expires_at,
        scopes: list[str] | None = None,
    ) -> None:
        self.calls.append((user_id, provider_id, email))


def _settings() -> Settings:
    # model_construct: ignore process env so local .env does not override test OAuth fields
    return Settings.model_construct(
        jwt_secret_key="unit-test-jwt-secret-key-min-32-chars!!",
        jwt_algorithm="HS256",
        access_token_expire_minutes=30,
        refresh_token_expire_days=7,
        google_oauth_client_id="test-client-id",
        google_oauth_client_secret="test-secret",
        google_oauth_redirect_uri="http://localhost:8000/api/v1/auth/oauth/google/callback",
    )


def test_build_authorize_url_contains_pkce_and_state() -> None:
    s = _settings()
    url = build_authorize_url(s)
    assert "accounts.google.com" in url
    assert "code_challenge=" in url
    assert "state=" in url
    assert "code_challenge_method=S256" in url


@pytest.mark.asyncio
async def test_complete_google_login_creates_user_and_tokens() -> None:
    s = _settings()
    verifier, _challenge = generate_pkce_pair()
    state = encode_oauth_state(s, verifier)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "oauth2.googleapis.com":
            return httpx.Response(
                200,
                json={
                    "access_token": "fake-access",
                    "expires_in": 3600,
                    "refresh_token": "fake-refresh",
                },
            )
        if "googleapis.com" in str(request.url) and "userinfo" in str(request.url):
            return httpx.Response(
                200,
                json={
                    "sub": "google-sub-1",
                    "email": "oauth-test@example.com",
                    "email_verified": True,
                    "name": "OAuth Tester",
                },
            )
        return httpx.Response(404, json={"error": str(request.url)})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        users = _FakeUsers()
        social = _FakeSocial()
        svc = GoogleOAuthService(s, users, social, http_client=client)
        access, refresh, user = await svc.complete_google_login("auth-code", state)

    assert access
    assert refresh
    assert user.email == "oauth-test@example.com"
    assert users.created and users.created[0][0] == "oauth-test@example.com"
    assert len(social.calls) == 1
    assert social.calls[0][1] == "google-sub-1"
