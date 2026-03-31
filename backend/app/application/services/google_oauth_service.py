from datetime import UTC, datetime, timedelta

import httpx

from app.config import Settings
from app.domain.entities.user import User
from app.domain.ports.social_account_repository import SocialAccountRepository
from app.domain.ports.user_repository import UserRepository
from app.infrastructure.auth.google_oauth_flow import (
    decode_oauth_state,
    exchange_code_for_tokens,
    fetch_google_userinfo,
)
from app.infrastructure.auth.jwt_handler import create_access_token, create_refresh_token
from app.infrastructure.auth.token_cipher import encrypt_optional, fernet_from_settings


class GoogleOAuthService:
    def __init__(
        self,
        settings: Settings,
        users: UserRepository,
        social: SocialAccountRepository,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings
        self._users = users
        self._social = social
        self._http = http_client

    async def complete_google_login(self, code: str, state: str) -> tuple[str, str, User]:
        code_verifier = decode_oauth_state(self._settings, state)
        tokens = await exchange_code_for_tokens(
            self._settings,
            code,
            code_verifier,
            client=self._http,
        )
        access = tokens.get("access_token")
        if not access or not isinstance(access, str):
            raise ValueError("Google token response missing access_token")
        refresh = tokens.get("refresh_token")
        refresh_str = refresh if isinstance(refresh, str) else None
        expires_at: datetime | None = None
        expires_in = tokens.get("expires_in")
        if isinstance(expires_in, int):
            expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)

        profile = await fetch_google_userinfo(access, client=self._http)
        if not profile.get("email_verified", False):
            raise ValueError("Google account email is not verified")
        email = profile.get("email")
        if not email or not isinstance(email, str):
            raise ValueError("Google did not return an email")
        sub = profile.get("sub")
        if not sub or not isinstance(sub, str):
            raise ValueError("Google did not return sub")
        raw_name = profile.get("name")
        display_name = raw_name if isinstance(raw_name, str) else None

        scope_raw = tokens.get("scope")
        scopes_list: list[str] = []
        if isinstance(scope_raw, str) and scope_raw.strip():
            scopes_list = scope_raw.split()

        user = await self._users.get_by_email(email)
        if user is None:
            user = await self._users.create_oauth_user(email, display_name)

        fernet = fernet_from_settings(self._settings)
        await self._social.upsert_google(
            user.id,
            sub,
            email,
            encrypt_optional(fernet, access),
            encrypt_optional(fernet, refresh_str),
            expires_at,
            scopes_list,
        )

        at = create_access_token(user.id, self._settings)
        rt = create_refresh_token(user.id, self._settings)
        return at, rt, user
