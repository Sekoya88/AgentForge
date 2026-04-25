"""S3-compatible object storage for audio blobs.

When ``S3_BUCKET`` is configured, audio is stored as objects instead of inline
base64 in PostgreSQL.  Falls back gracefully: if no bucket is set the helper
functions return ``None`` so callers can keep using the legacy base64 path.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import aioboto3

if TYPE_CHECKING:
    from types_aiobotocore_s3.client import S3Client

    from app.config import Settings

_session: aioboto3.Session | None = None


def _get_session() -> aioboto3.Session:
    global _session  # noqa: PLW0603
    if _session is None:
        _session = aioboto3.Session()
    return _session


class S3AudioStore:
    """Thin async wrapper around S3 put/get/presign for audio blobs."""

    def __init__(self, settings: Settings) -> None:
        self._bucket = settings.s3_bucket or ""
        self._endpoint = settings.s3_endpoint_url
        self._region = settings.s3_region
        self._access_key = settings.s3_access_key
        self._secret_key = settings.s3_secret_key

    @property
    def enabled(self) -> bool:
        return bool(self._bucket)

    def _client_kwargs(self) -> dict:
        kw: dict = {
            "region_name": self._region,
        }
        if self._endpoint:
            kw["endpoint_url"] = self._endpoint
        if self._access_key:
            kw["aws_access_key_id"] = self._access_key
        if self._secret_key:
            kw["aws_secret_access_key"] = self._secret_key
        return kw

    async def upload(self, data: bytes, *, prefix: str = "audio", ext: str = "bin") -> str:
        """Upload *data* and return the object key (``prefix/uuid.ext``)."""
        key = f"{prefix}/{uuid.uuid4().hex}.{ext}"
        session = _get_session()
        async with session.client("s3", **self._client_kwargs()) as s3:  # type: ignore[arg-type]
            s3: S3Client
            await s3.put_object(Bucket=self._bucket, Key=key, Body=data)
        return key

    async def download(self, key: str) -> bytes:
        """Download object by key and return raw bytes."""
        session = _get_session()
        async with session.client("s3", **self._client_kwargs()) as s3:  # type: ignore[arg-type]
            s3: S3Client
            resp = await s3.get_object(Bucket=self._bucket, Key=key)
            return await resp["Body"].read()

    async def presigned_url(self, key: str, *, expires_in: int = 3600) -> str:
        """Generate a presigned GET URL for the given key."""
        session = _get_session()
        async with session.client("s3", **self._client_kwargs()) as s3:  # type: ignore[arg-type]
            s3: S3Client
            return await s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": key},
                ExpiresIn=expires_in,
            )
