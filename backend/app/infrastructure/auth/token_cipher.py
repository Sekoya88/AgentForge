"""Symmetric encryption for OAuth tokens (same key derivation as user API secrets)."""

import base64
import hashlib

from cryptography.fernet import Fernet

from app.config import Settings


def fernet_from_settings(settings: Settings) -> Fernet:
    key = hashlib.sha256(settings.jwt_secret_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt_optional(fernet: Fernet, value: str | None) -> str | None:
    if not value:
        return None
    return fernet.encrypt(value.encode()).decode()


def decrypt_optional(fernet: Fernet, value: str | None) -> str | None:
    if not value:
        return None
    try:
        return fernet.decrypt(value.encode()).decode()
    except Exception:
        return None
