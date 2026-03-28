import base64
import hashlib
from uuid import UUID

from cryptography.fernet import Fernet

from app.config import get_settings
from app.domain.ports.user_secrets_repository import UserSecretsDict, UserSecretsRepository


class SecretsService:
    def __init__(self, repo: UserSecretsRepository):
        self._repo = repo
        self._fernet = self._init_fernet()

    def _init_fernet(self) -> Fernet:
        settings = get_settings()
        key = hashlib.sha256(settings.jwt_secret_key.encode()).digest()
        return Fernet(base64.urlsafe_b64encode(key))

    def _encrypt(self, value: str | None) -> str | None:
        if not value:
            return None
        return self._fernet.encrypt(value.encode()).decode()

    def _decrypt(self, value: str | None) -> str | None:
        if not value:
            return None
        try:
            return self._fernet.decrypt(value.encode()).decode()
        except Exception:
            return None

    async def get_decrypted_secrets(self, user_id: UUID) -> UserSecretsDict:
        enc_secrets = await self._repo.get_secrets(user_id)
        return {
            "openai_key": self._decrypt(enc_secrets["openai_key"]),
            "google_key": self._decrypt(enc_secrets["google_key"]),
            "anthropic_key": self._decrypt(enc_secrets.get("anthropic_key")),
        }

    async def update_secrets(
        self,
        user_id: UUID,
        openai_key: str | None,
        google_key: str | None,
        anthropic_key: str | None = None,
    ) -> None:
        enc_openai = self._encrypt(openai_key)
        enc_google = self._encrypt(google_key)
        enc_anthropic = self._encrypt(anthropic_key)
        await self._repo.update_secrets(user_id, enc_openai, enc_google, enc_anthropic)
