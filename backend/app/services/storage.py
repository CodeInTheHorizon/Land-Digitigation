"""Object storage abstraction – local filesystem for dev, MinIO/S3 for production."""

from __future__ import annotations

import io
import os
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class StorageService(ABC):
    """Abstract interface for object storage."""

    @abstractmethod
    async def upload(self, path: str, data: bytes, content_type: str) -> str:
        """Upload bytes and return the storage path."""
        ...

    @abstractmethod
    async def download(self, path: str) -> bytes:
        """Download and return file bytes."""
        ...

    @abstractmethod
    async def delete(self, path: str) -> None:
        """Delete an object."""
        ...

    @abstractmethod
    async def exists(self, path: str) -> bool:
        """Check whether an object exists."""
        ...

    @abstractmethod
    async def get_presigned_url(self, path: str, expires_secs: int = 3600) -> str:
        """Generate a presigned download URL."""
        ...


# ---------------------------------------------------------------------------
# Local filesystem storage (development)
# ---------------------------------------------------------------------------

class LocalStorageService(StorageService):
    """Store files on the local filesystem under a configurable base directory."""

    def __init__(self, base_dir: str | None = None) -> None:
        self.base_dir = Path(base_dir or os.getenv("LOCAL_STORAGE_DIR", "uploads"))
        self.base_dir.mkdir(parents=True, exist_ok=True)
        logger.info("storage.local_init", base_dir=str(self.base_dir))

    def _resolve(self, path: str) -> Path:
        """Resolve and validate storage path – guards against traversal."""
        resolved = (self.base_dir / path).resolve()
        if not str(resolved).startswith(str(self.base_dir.resolve())):
            raise ValueError(f"Path traversal detected: {path!r}")
        return resolved

    async def upload(self, path: str, data: bytes, content_type: str) -> str:
        target = self._resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return path

    async def download(self, path: str) -> bytes:
        target = self._resolve(path)
        if not target.is_file():
            raise FileNotFoundError(f"Object not found: {path}")
        return target.read_bytes()

    async def delete(self, path: str) -> None:
        target = self._resolve(path)
        if target.is_file():
            target.unlink()

    async def exists(self, path: str) -> bool:
        return self._resolve(path).is_file()

    async def get_presigned_url(self, path: str, expires_secs: int = 3600) -> str:
        # Local storage has no real presigned URLs; return a relative path.
        return f"/storage/{path}"


# ---------------------------------------------------------------------------
# MinIO / S3-compatible storage (production)
# ---------------------------------------------------------------------------

class MinIOStorageService(StorageService):
    """MinIO / S3-compatible storage using the minio SDK."""

    def __init__(self) -> None:
        from minio import Minio

        self.client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_USE_SSL,
        )
        self.bucket = settings.MINIO_BUCKET
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)
            logger.info("storage.bucket_created", bucket=self.bucket)

    async def upload(self, path: str, data: bytes, content_type: str) -> str:
        self.client.put_object(
            self.bucket,
            path,
            io.BytesIO(data),
            length=len(data),
            content_type=content_type,
        )
        return path

    async def download(self, path: str) -> bytes:
        response = self.client.get_object(self.bucket, path)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    async def delete(self, path: str) -> None:
        self.client.remove_object(self.bucket, path)

    async def exists(self, path: str) -> bool:
        try:
            self.client.stat_object(self.bucket, path)
            return True
        except Exception:
            return False

    async def get_presigned_url(self, path: str, expires_secs: int = 3600) -> str:
        from datetime import timedelta

        return self.client.presigned_get_object(
            self.bucket, path, expires=timedelta(seconds=expires_secs)
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_storage_instance: Optional[StorageService] = None


def get_storage_service() -> StorageService:
    """Return a singleton storage service based on config.

    Defaults to local storage in development for zero-dependency startup.
    """
    global _storage_instance
    if _storage_instance is None:
        backend = settings.STORAGE_BACKEND.lower()
        if backend == "local":
            _storage_instance = LocalStorageService()
        elif backend in ("minio", "s3"):
            _storage_instance = MinIOStorageService()
        else:
            logger.warning(
                "storage.unknown_backend",
                backend=backend,
                fallback="local",
            )
            _storage_instance = LocalStorageService()
    return _storage_instance


def reset_storage_service() -> None:
    """Reset singleton – used in tests."""
    global _storage_instance
    _storage_instance = None
