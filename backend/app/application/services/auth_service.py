import bcrypt

from app.config import Settings
from app.domain.entities.user import User
from app.domain.exceptions import InvalidCredentialsError, UserAlreadyExistsError
from app.domain.ports.user_repository import UserRepository
from app.infrastructure.auth.jwt_handler import (
    create_access_token,
    create_refresh_token,
    decode_token,
)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


class AuthService:
    def __init__(self, users: UserRepository, settings: Settings) -> None:
        self._users = users
        self._settings = settings

    async def register(self, email: str, password: str, display_name: str | None) -> User:
        existing = await self._users.get_by_email(email)
        if existing:
            raise UserAlreadyExistsError(email)
        pw_hash = hash_password(password)
        return await self._users.save(email, pw_hash, display_name)

    async def login(self, email: str, password: str) -> tuple[str, str, User]:
        row = await self._users.get_credentials_by_email(email)
        if row is None:
            raise InvalidCredentialsError()
        user, pw_hash = row
        if not verify_password(password, pw_hash):
            raise InvalidCredentialsError()
        access = create_access_token(user.id, self._settings)
        refresh = create_refresh_token(user.id, self._settings)
        return access, refresh, user

    def refresh(self, refresh_token: str) -> str:
        user_id = decode_token(refresh_token, self._settings, expect_typ="refresh")
        return create_access_token(user_id, self._settings)
