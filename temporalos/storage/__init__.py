"""Storage abstraction layer — local filesystem or S3/MinIO.

Provides a unified interface for storing and retrieving files across
different backends: local filesystem (default) and S3-compatible storage.

Usage:
    from temporalos.storage import get_storage
    storage = get_storage()
    await storage.put("uploads/video.mp4", data)
    data = await storage.get("uploads/video.mp4")
"""

from __future__ import annotations

import logging
import os
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class StorageBackend(ABC):
    """Abstract storage interface."""

    @abstractmethod
    async def put(self, key: str, data: bytes) -> str:
        """Store data, return the storage URI."""
        ...

    @abstractmethod
    async def get(self, key: str) -> bytes:
        """Retrieve data by key."""
        ...

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete data by key, return True if deleted."""
        ...

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if a key exists."""
        ...

    @abstractmethod
    async def list_keys(self, prefix: str = "") -> list[str]:
        """List keys with the given prefix."""
        ...

    async def presign_put(self, key: str, expires_in: int = 3600, content_type: Optional[str] = None) -> dict:
        """Return a presigned PUT upload URL (if supported).

        Backends that cannot generate presigned URLs should return a fallback
        descriptor instructing clients to use the regular upload endpoint.
        """
        raise NotImplementedError

    async def presign_get(self, key: str, expires_in: int = 3600) -> str:
        """Return a presigned GET download URL."""
        raise NotImplementedError


class LocalStorage(StorageBackend):
    """Local filesystem storage backend."""

    def __init__(self, base_dir: str = "/tmp/temporalos/storage") -> None:
        self._base = Path(base_dir)
        self._base.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        # Prevent path traversal
        safe_key = Path(key).as_posix().lstrip("/")
        resolved = (self._base / safe_key).resolve()
        if not str(resolved).startswith(str(self._base.resolve())):
            raise ValueError(f"Invalid key: {key}")
        return resolved

    async def put(self, key: str, data: bytes) -> str:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return f"file://{p}"

    async def get(self, key: str) -> bytes:
        p = self._path(key)
        if not p.exists():
            raise FileNotFoundError(f"Key not found: {key}")
        return p.read_bytes()

    async def delete(self, key: str) -> bool:
        p = self._path(key)
        if p.exists():
            p.unlink()
            return True
        return False

    async def exists(self, key: str) -> bool:
        return self._path(key).exists()

    async def presign_put(self, key: str, expires_in: int = 3600, content_type: Optional[str] = None) -> dict:
        # Local backend has no presigning; instruct the client to fall back to the
        # regular multipart upload endpoint. Keeps the API surface consistent.
        return {
            "mode": "fallback",
            "method": "POST",
            "upload_url": "/api/v1/uploads/direct",
            "fields": {"key": key},
            "key": key,
            "reason": "local storage backend — use POST upload",
        }

    async def presign_get(self, key: str, expires_in: int = 3600) -> str:
        p = self._path(key)
        if not p.exists():
            raise FileNotFoundError(f"Key not found: {key}")
        return f"file://{p}"

    async def list_keys(self, prefix: str = "") -> list[str]:
        base = self._path(prefix) if prefix else self._base
        if not base.exists():
            return []
        results = []
        for p in base.rglob("*"):
            if p.is_file():
                results.append(str(p.relative_to(self._base)))
        return sorted(results)


class S3Storage(StorageBackend):
    """S3/MinIO compatible storage backend.

    Requires ``boto3`` package.
    """

    def __init__(
        self,
        bucket: str = "temporalos",
        endpoint_url: Optional[str] = None,
        region: str = "us-east-1",
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
    ) -> None:
        import boto3  # type: ignore[import-untyped]

        self._bucket = bucket
        kwargs: dict = {"region_name": region}
        if endpoint_url:
            kwargs["endpoint_url"] = endpoint_url
        if access_key and secret_key:
            kwargs["aws_access_key_id"] = access_key
            kwargs["aws_secret_access_key"] = secret_key

        self._client = boto3.client("s3", **kwargs)
        # Ensure bucket exists
        try:
            self._client.head_bucket(Bucket=bucket)
        except Exception:
            try:
                self._client.create_bucket(Bucket=bucket)
            except Exception as e:
                logger.warning("Could not create bucket %s: %s", bucket, e)

    async def put(self, key: str, data: bytes) -> str:
        import asyncio
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None, lambda: self._client.put_object(Bucket=self._bucket, Key=key, Body=data)
        )
        return f"s3://{self._bucket}/{key}"

    async def get(self, key: str) -> bytes:
        import asyncio
        loop = asyncio.get_event_loop()

        def _get() -> bytes:
            resp = self._client.get_object(Bucket=self._bucket, Key=key)
            return resp["Body"].read()

        return await loop.run_in_executor(None, _get)

    async def delete(self, key: str) -> bool:
        import asyncio
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                None, lambda: self._client.delete_object(Bucket=self._bucket, Key=key)
            )
            return True
        except Exception:
            return False

    async def exists(self, key: str) -> bool:
        import asyncio
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                None, lambda: self._client.head_object(Bucket=self._bucket, Key=key)
            )
            return True
        except Exception:
            return False

    async def presign_put(self, key: str, expires_in: int = 3600, content_type: Optional[str] = None) -> dict:
        import asyncio
        loop = asyncio.get_event_loop()

        def _presign() -> dict:
            params: dict = {"Bucket": self._bucket, "Key": key}
            if content_type:
                params["ContentType"] = content_type
            url = self._client.generate_presigned_url(
                "put_object",
                Params=params,
                ExpiresIn=expires_in,
            )
            return {
                "mode": "s3",
                "method": "PUT",
                "upload_url": url,
                "key": key,
                "expires_in": expires_in,
                "content_type": content_type,
                "bucket": self._bucket,
            }

        return await loop.run_in_executor(None, _presign)

    async def presign_get(self, key: str, expires_in: int = 3600) -> str:
        import asyncio
        loop = asyncio.get_event_loop()

        def _gen() -> str:
            return self._client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": key},
                ExpiresIn=expires_in,
            )

        return await loop.run_in_executor(None, _gen)

    async def list_keys(self, prefix: str = "") -> list[str]:
        import asyncio
        loop = asyncio.get_event_loop()

        def _list() -> list[str]:
            keys: list[str] = []
            paginator = self._client.get_paginator("list_objects_v2")
            kw = {"Bucket": self._bucket}
            if prefix:
                kw["Prefix"] = prefix
            for page in paginator.paginate(**kw):
                for obj in page.get("Contents", []):
                    keys.append(obj["Key"])
            return keys

        return await loop.run_in_executor(None, _list)


# ── Factory ────────────────────────────────────────────────────────────────────

_instance: Optional[StorageBackend] = None


def get_storage() -> StorageBackend:
    """Return the configured storage backend (singleton)."""
    global _instance
    if _instance is not None:
        return _instance

    backend = os.environ.get("STORAGE_BACKEND", "local").lower()

    if backend == "s3":
        _instance = S3Storage(
            bucket=os.environ.get("S3_BUCKET", "temporalos"),
            endpoint_url=os.environ.get("S3_ENDPOINT_URL"),
            region=os.environ.get("S3_REGION", "us-east-1"),
            access_key=os.environ.get("AWS_ACCESS_KEY_ID"),
            secret_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
        )
    else:
        _instance = LocalStorage(
            base_dir=os.environ.get("STORAGE_LOCAL_DIR", "/tmp/temporalos/storage")
        )

    return _instance


def reset_storage() -> None:
    """Reset singleton (useful for tests)."""
    global _instance
    _instance = None
