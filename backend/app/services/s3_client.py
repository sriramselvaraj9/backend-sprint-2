"""
backend/app/services/s3_client.py

S3 Client initialization, configuration, data models, and centralized error handling.
Extracted from storage_service to separate client infrastructure from business operations.
"""

import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from typing import Any, NoReturn

import boto3
from botocore.exceptions import ClientError

from app.core.config import Settings
from app.exceptions.domain import (
    StorageAccessDenied,
    StorageBucketNotFound,
    StorageObjectNotFound,
    StorageOperationError,
)

logger = logging.getLogger("storage_service")


@dataclass
class StoredFile:
    """Represents a retrieved stored file with asynchronous streaming capability."""

    file_id: str
    key: str
    filename: str
    content_type: str
    size: int
    last_modified: datetime | None
    metadata: dict[str, str]
    stream: AsyncIterator[bytes]

    async def read(self) -> bytes:
        """Read all streamed chunks into memory."""
        return b"".join([chunk async for chunk in self.stream])


def create_s3_client(cfg: Settings) -> Any:
    """Create a configured Boto3 S3 client using centralized settings."""
    return boto3.client(
        "s3",
        region_name=cfg.AWS_REGION or cfg.AWS_DEFAULT_REGION,
        aws_access_key_id=cfg.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=cfg.AWS_SECRET_ACCESS_KEY,
        endpoint_url=cfg.S3_ENDPOINT_URL or cfg.AWS_ENDPOINT_URL,
    )


def handle_s3_client_error(
    exc: ClientError,
    bucket_name: str,
    file_id: str | None = None,
    key: str | None = None,
) -> NoReturn:
    """
    Translate raw AWS S3 ClientError responses into structured domain exceptions.
    Ensures raw AWS errors never leak directly to the client.
    """
    code = exc.response.get("Error", {}).get("Code", "")
    msg = exc.response.get("Error", {}).get("Message", str(exc))
    logger.error(f"[STORAGE] S3 ClientError: code={code}, key={key}, file_id={file_id}, msg={msg}")

    if code in ("NoSuchKey", "404", "NotFound"):
        target = file_id or key or "unknown"
        raise StorageObjectNotFound(
            file_id=target,
            key=key,
            message=f"Stored object '{target}' was not found in bucket '{bucket_name}'.",
        ) from exc

    if code == "NoSuchBucket":
        raise StorageBucketNotFound(
            bucket_name=bucket_name,
            message=f"Storage bucket '{bucket_name}' does not exist.",
        ) from exc

    if code in ("AccessDenied", "UnauthorizedOperation", "AccessDeniedException"):
        raise StorageAccessDenied(
            message="Access denied to S3 storage resource.",
            detail={"code": code, "bucket": bucket_name},
        ) from exc

    raise StorageOperationError(
        message=f"Storage operation failed ({code}): {msg}",
        detail={"code": code, "bucket": bucket_name},
    ) from exc

