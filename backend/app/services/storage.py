"""Object storage abstraction for audio (learner recordings and synthesized listening audio).

- `local` (development): files under STORAGE_LOCAL_DIR
- `s3` (production): any S3-compatible bucket (AWS S3, Cloudflare R2, MinIO, ...)

Files are always served back through authenticated API endpoints, never via public URLs.
"""

from __future__ import annotations

import logging
import re
import shutil
from pathlib import Path
from typing import Protocol

from app.core.config import settings

logger = logging.getLogger("linguasi.storage")

_SAFE_KEY = re.compile(r"^[A-Za-z0-9/_\-.]+$")


def _validate_key(key: str) -> str:
    if not key or ".." in key or key.startswith("/") or not _SAFE_KEY.match(key):
        raise ValueError(f"Unsafe storage key: {key!r}")
    return key


class StorageBackend(Protocol):
    def save(self, key: str, data: bytes, content_type: str) -> str: ...
    def read(self, key: str) -> bytes: ...
    def exists(self, key: str) -> bool: ...
    def delete(self, key: str) -> None: ...
    def delete_prefix(self, prefix: str) -> None: ...


class LocalStorage:
    def __init__(self, root: str) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        path = (self.root / _validate_key(key)).resolve()
        if self.root not in path.parents:
            raise ValueError("Storage key escapes storage root")
        return path

    def save(self, key: str, data: bytes, content_type: str) -> str:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    def read(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def exists(self, key: str) -> bool:
        try:
            return self._path(key).is_file()
        except ValueError:
            return False

    def delete(self, key: str) -> None:
        try:
            self._path(key).unlink(missing_ok=True)
        except ValueError:
            return

    def delete_prefix(self, prefix: str) -> None:
        target = (self.root / _validate_key(prefix.rstrip("/"))).resolve()
        if self.root in target.parents and target.is_dir():
            shutil.rmtree(target, ignore_errors=True)


class S3Storage:
    def __init__(self) -> None:
        import boto3  # lazy import: only needed in production

        if not settings.s3_bucket:
            raise RuntimeError("STORAGE_BACKEND=s3 requires S3_BUCKET")
        self.bucket = settings.s3_bucket
        self.client = boto3.client(
            "s3",
            region_name=settings.s3_region,
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
        )

    def save(self, key: str, data: bytes, content_type: str) -> str:
        self.client.put_object(Bucket=self.bucket, Key=_validate_key(key), Body=data, ContentType=content_type)
        return key

    def read(self, key: str) -> bytes:
        obj = self.client.get_object(Bucket=self.bucket, Key=_validate_key(key))
        return obj["Body"].read()

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=_validate_key(key))
            return True
        except Exception:
            return False

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=_validate_key(key))

    def delete_prefix(self, prefix: str) -> None:
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=_validate_key(prefix)):
            keys = [{"Key": obj["Key"]} for obj in page.get("Contents", [])]
            if keys:
                self.client.delete_objects(Bucket=self.bucket, Delete={"Objects": keys})


def _build_storage() -> StorageBackend:
    if settings.storage_backend == "s3":
        return S3Storage()
    return LocalStorage(settings.storage_local_dir)


class _LazyStorage:
    """Defers backend construction until first use (keeps imports cheap and tests configurable)."""

    _backend: StorageBackend | None = None

    def _get(self) -> StorageBackend:
        if self._backend is None:
            self._backend = _build_storage()
        return self._backend

    def __getattr__(self, name: str):
        return getattr(self._get(), name)


storage: StorageBackend = _LazyStorage()  # type: ignore[assignment]
