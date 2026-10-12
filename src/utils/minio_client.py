"""MinIO client helpers for the air-quality data lake."""

from __future__ import annotations

import io
import os
from typing import Any

from minio import Minio
from minio.error import S3Error


def _env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None or value == "":
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def get_minio_client(
    endpoint: str | None = None,
    access_key: str | None = None,
    secret_key: str | None = None,
    secure: bool | None = None,
) -> Minio:
    """Build a MinIO client from args or environment."""
    ep = endpoint or os.getenv("MINIO_ENDPOINT") or "localhost:9000"
    # Allow host:port or http(s)://host:port
    ep = ep.removeprefix("https://").removeprefix("http://")

    if secure is None:
        secure = (os.getenv("MINIO_SECURE") or "false").lower() in {"1", "true", "yes"}

    ak = (
        access_key
        or os.getenv("MINIO_ACCESS_KEY")
        or os.getenv("MINIO_ROOT_USER")
        or "minioadmin"
    )
    sk = (
        secret_key
        or os.getenv("MINIO_SECRET_KEY")
        or os.getenv("MINIO_ROOT_PASSWORD")
        or "minioadmin"
    )

    return Minio(ep, access_key=ak, secret_key=sk, secure=secure)


def get_bucket(bucket: str | None = None) -> str:
    return bucket or _env("MINIO_BUCKET", "air-quality-lake")


def ensure_bucket(client: Minio, bucket: str | None = None) -> bool:
    """Create the lake bucket if missing (same result as scripts/infra/init_minio.sh).

    Returns True when the bucket was created, False when it already existed.
    """
    name = get_bucket(bucket)
    if client.bucket_exists(name):
        return False
    client.make_bucket(name)
    return True


def object_exists(client: Minio, bucket: str, object_name: str) -> bool:
    try:
        client.stat_object(bucket, object_name)
        return True
    except S3Error as exc:
        if exc.code in {"NoSuchKey", "NoSuchObject", "NoSuchBucket", "NotFound"}:
            return False
        # Some MinIO builds surface missing objects as 404 without NoSuchKey
        status = getattr(exc, "status", None)
        if status == 404:
            return False
        raise


def put_bytes(
    client: Minio,
    bucket: str,
    object_name: str,
    data: bytes,
    content_type: str = "application/octet-stream",
    metadata: dict[str, str] | None = None,
) -> Any:
    """Upload bytes. Caller must enforce no-overwrite policy before calling."""
    return client.put_object(
        bucket,
        object_name,
        io.BytesIO(data),
        length=len(data),
        content_type=content_type,
        metadata=metadata,
    )


def put_file(
    client: Minio,
    bucket: str,
    object_name: str,
    file_path: str,
    content_type: str = "text/csv",
    metadata: dict[str, str] | None = None,
) -> Any:
    """Upload a local file. Caller must enforce no-overwrite policy before calling."""
    return client.fput_object(
        bucket,
        object_name,
        file_path,
        content_type=content_type,
        metadata=metadata,
    )


def get_object_bytes(client: Minio, bucket: str, object_name: str) -> bytes:
    response = client.get_object(bucket, object_name)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


def get_object_metadata(client: Minio, bucket: str, object_name: str) -> dict[str, str]:
    stat = client.stat_object(bucket, object_name)
    # MinIO returns user metadata with lowercase keys, often prefixed with x-amz-meta-
    raw = dict(stat.metadata or {})
    cleaned: dict[str, str] = {}
    for key, value in raw.items():
        k = key.lower()
        if k.startswith("x-amz-meta-"):
            k = k[len("x-amz-meta-") :]
        cleaned[k] = value if isinstance(value, str) else str(value)
    return cleaned


def list_object_names(client: Minio, bucket: str, prefix: str = "") -> list[str]:
    return [obj.object_name for obj in client.list_objects(bucket, prefix=prefix, recursive=True)]
