"""
backend/app/services/storage_service.py

Asynchronous S3 Storage Service.
Coordinates file uploads, chunked streaming downloads, prefix listing, and safe deletions.
Low-level S3 client creation and error mapping are encapsulated in app.services.s3_client.
"""

import asyncio
import io
import logging
import os
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import IO, Any, NoReturn

from botocore.exceptions import ClientError
from starlette.datastructures import UploadFile

from app.core.config import Settings
from app.core.config import settings as app_settings
from app.exceptions.domain import (
    BucketNotFoundError,
    FileNotFoundError,
    StorageAccessDenied,
    StorageBucketNotFound,
    StorageError,
    StorageObjectNotFound,
    StorageOperationError,
    StoragePermissionDenied,
    StorageValidationError,
    UploadFailedError,
)
from app.schemas.storage import (
    FileDeleteResponse,
    FileListItem,
    FileListResponse,
    FileUploadResponse,
    PresignedUrlsResponse,
    StoragePresignedOperation,
    StoragePresignedUrlResponse,
)
from app.services.s3_client import StoredFile, create_s3_client, handle_s3_client_error

logger = logging.getLogger("storage_service")

__all__ = [
    "StorageService",
    "StoredFile",
    "StoragePresignedOperation",
    "StoragePresignedUrlResponse",
    "PresignedUrlsResponse",
]


class StorageService:
    """S3 storage service managing file upload, retrieval, streaming, listing, deletion, and presigned URLs."""

    def __init__(
        self,
        settings: Settings | None = None,
        s3_client: Any | None = None,
        bucket_name: str | None = None,
        default_prefix: str | None = None,
        presigned_client: Any | None = None,
    ) -> None:
        cfg = settings or app_settings
        self.settings = cfg
        self.bucket_name = bucket_name or cfg.S3_BUCKET_NAME
        self.default_prefix = default_prefix or cfg.S3_DEFAULT_PREFIX
        self._s3_client = s3_client or create_s3_client(cfg)
        self._presigned_client = presigned_client
        self.logger = logger

    @property
    def s3_client(self) -> Any:
        return self._s3_client

    @s3_client.setter
    def s3_client(self, value: Any) -> None:
        self._s3_client = value

    @property
    def client(self) -> Any:
        return self._s3_client

    @client.setter
    def client(self, value: Any) -> None:
        self._s3_client = value

    @property
    def presigned_client(self) -> Any:
        return self._presigned_client or self._s3_client

    @presigned_client.setter
    def presigned_client(self, value: Any) -> None:
        self._presigned_client = value

    def _create_s3_client(self, cfg: Settings) -> Any:
        return create_s3_client(cfg)

    def _handle_client_error(
        self,
        exc: ClientError,
        file_id: str | None = None,
        key: str | None = None,
    ) -> NoReturn:
        handle_s3_client_error(exc, self.bucket_name, file_id=file_id, key=key)

    def _sync_resolve_key(self, file_id: str) -> str:
        """Resolve a file_id or exact object key to the existing S3 key."""
        if not file_id:
            raise StorageObjectNotFound(file_id=file_id,message="File identifier cannot be empty.")

        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=file_id)
            logger.info(f"Found file with ID {file_id}")
            return file_id
        except ClientError as e:
            if e.response.get("Error", {}).get("Code", "") not in ("404", "NoSuchKey", "NotFound"):
                self._handle_client_error(e, file_id=file_id)

        for prefix in (f"{self.default_prefix}/{file_id}/", f"{file_id}/"):
            try:
                resp = self.s3_client.list_objects_v2(Bucket=self.bucket_name, Prefix=prefix, MaxKeys=1)
                if contents := resp.get("Contents"):
                    return contents[0]["Key"]
            except ClientError as e:
                self._handle_client_error(e, file_id=file_id)

        raise StorageObjectNotFound(file_id=file_id, message=f"No stored file found matching ID '{file_id}'.")

    def _sync_upload_object(self, file_obj: Any, key: str, extra_args: dict[str, Any]) -> None:
        try:
            self.s3_client.upload_fileobj(Fileobj=file_obj, Bucket=self.bucket_name, Key=key, ExtraArgs=extra_args)
        except ClientError as e:
            self._handle_client_error(e, key=key)

    def _sync_get_object(self, file_id: str) -> tuple[str, dict[str, Any]]:
        key = self._sync_resolve_key(file_id)
        try:
            return key, self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
        except ClientError as e:
            self._handle_client_error(e, key=key)

    def _sync_delete_object(self, file_id: str) -> str:
        key = self._sync_resolve_key(file_id)
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=key)
            return key
        except ClientError as e:
            self._handle_client_error(e, key=key)

    def _sync_list_objects(
        self,
        prefix: str | None = None,
        max_keys: int | None = None,
        continuation_token: str | None = None,
    ) -> tuple[list[FileListItem], str | None, bool]:
        kwargs: dict[str, Any] = {"Bucket": self.bucket_name}
        if prefix:
            kwargs["Prefix"] = prefix
        if max_keys is not None:
            kwargs["MaxKeys"] = max_keys
        if continuation_token:
            kwargs["ContinuationToken"] = continuation_token

        items: list[FileListItem] = []
        try:
            while True:
                resp = self.s3_client.list_objects_v2(**kwargs)
                for obj in resp.get("Contents", []):
                    items.append(
                        FileListItem(
                            key=obj["Key"],
                            size=obj["Size"],
                            last_modified=obj["LastModified"],
                            etag=obj.get("ETag", "").strip('"'),
                        )
                    )
                token = resp.get("NextContinuationToken")
                is_truncated = resp.get("IsTruncated", False)
                if max_keys is not None or not is_truncated or not token:
                    return items, token, is_truncated
                kwargs["ContinuationToken"] = token
        except ClientError as e:
            self._handle_client_error(e)

    async def _stream_body(self, body: Any, chunk_size: int = 64 * 1024) -> AsyncIterator[bytes]:
        try:
            if hasattr(body, "read") and callable(body.read):
                while True:
                    chunk = await asyncio.to_thread(body.read, chunk_size)
                    if not chunk:
                        break
                    yield bytes(chunk)
            elif isinstance(body, (bytes, bytearray)):
                yield bytes(body)
        finally:
            if hasattr(body, "close") and callable(body.close):
                await asyncio.to_thread(body.close)

    async def upload_file(
        self,
        file: UploadFile | IO[bytes] | bytes,
        filename: str | None = None,
        content_type: str | None = None,
        prefix: str | None = None,
    ) -> FileUploadResponse:
        file_id = str(uuid.uuid4())
        name = Path(filename or getattr(file, "filename", None) or getattr(file, "name", "file")).name or "file"
        ctype = content_type or getattr(file, "content_type", None) or "application/octet-stream"

        if hasattr(file, "file"):
            if hasattr(file, "seek") and asyncio.iscoroutinefunction(file.seek):
                await file.seek(0)
            file_obj = getattr(file, "file")
        elif isinstance(file, bytes):
            file_obj = io.BytesIO(file)
        else:
            file_obj = file

        # pyrefly: ignore[bad-argument-count]
        file_obj.seek(0, os.SEEK_END) #Moves the read pointer straight to the last byte of the file.
        # pyrefly: ignore[missing-attribute]
        size = file_obj.tell() #Returns the current byte number of the pointer. Since the pointer is at the very end, this number equals the exact total size of the file in bytes (26,937 bytes).
        file_obj.seek(0) #Moves the pointer back to the very start (byte 0). If you don't rewind it, Boto3 will try to upload from the end of the file and upload 0 bytes!

        prefix = prefix or self.default_prefix
        key = f"{prefix}/{file_id}/{name}"
        extra_args = {"ContentType": ctype, "Metadata": {"original-filename": name, "file-id": file_id}}

        await asyncio.to_thread(self._sync_upload_object, file_obj, key, extra_args)
        logger.info(f"[STORAGE] File uploaded successfully: id={file_id}, key={key}")

        return FileUploadResponse(
            file_id=file_id,
            filename=name,
            content_type=ctype,
            size=size,
            key=key,
            uploaded_at=datetime.now(UTC),
        )

    async def get_file(self, file_id: str) -> StoredFile:
        key, response = await asyncio.to_thread(self._sync_get_object, file_id)
        metadata = response.get("Metadata", {})
        filename = metadata.get("original-filename") or Path(key).name

        return StoredFile(
            file_id=file_id,
            key=key,
            filename=filename,
            content_type=response.get("ContentType", "application/octet-stream"),
            size=int(response.get("ContentLength", 0)),
            last_modified=response.get("LastModified"),
            metadata=metadata,
            stream=self._stream_body(response.get("Body")),
        )

    async def list_files(
        self,
        prefix: str | None = None,
        max_keys: int | None = None,
        continuation_token: str | None = None,
    ) -> FileListResponse:
        file_items, token, is_truncated = await asyncio.to_thread(
            self._sync_list_objects, prefix, max_keys, continuation_token
        )
        return FileListResponse(
            files=file_items,
            total=len(file_items),
            prefix=prefix,
            next_continuation_token=token,
            is_truncated=is_truncated,
        )

    async def delete_file(self, file_id: str) -> FileDeleteResponse:
        key = await asyncio.to_thread(self._sync_delete_object, file_id)
        logger.info(f"[STORAGE] File deleted successfully: id={file_id}, key={key}")

        return FileDeleteResponse(
            file_id=file_id,
            key=key,
            deleted=True,
            message=f"File '{file_id}' successfully deleted",
        )

    # ---------------------------------------------------------------------------
    # Presigned URL Implementation
    # ---------------------------------------------------------------------------

    async def generate_presigned_url(
        self,
        object_key: str,
        operation: StoragePresignedOperation = StoragePresignedOperation.DOWNLOAD,
        expiry: int | None = None,
        content_type: str | None = None,
        file_size: int | None = None,
        content_disposition: str = "attachment",
    ) -> StoragePresignedUrlResponse:
        normalized_key = self._normalize_object_key(object_key)
        expires_in = expiry if expiry is not None else int(self.settings.PRESIGNED_URL_EXPIRE_SECONDS)
        filename = normalized_key.rsplit("/", 1)[-1]
        params: dict[str, Any] = {"Bucket": self.bucket_name, "Key": normalized_key}
        required_headers: dict[str, str] = {}

        if operation is StoragePresignedOperation.UPLOAD:
            if not content_type:
                raise StorageValidationError(message="Missing content type for upload validation.")
            if file_size is None or file_size <= 0:
                raise StorageValidationError(message="A positive file size is required for uploads.")
            self._validate_file_size(file_size)
            self._validate_allowed_content_type(content_type)
            content_disposition = self._inline_disposition(filename)
            params.update(
                {
                    "ContentType": content_type,
                    "ContentDisposition": content_disposition,
                }
            )
            required_headers = {
                "Content-Type": content_type,
                "Content-Disposition": content_disposition,
            }
        else:
            if content_disposition not in {"attachment", "inline"}:
                raise StorageValidationError(
                    message="content_disposition must be 'attachment' or 'inline'."
                )
            disposition = (
                self._attachment_disposition(filename)
                if content_disposition == "attachment"
                else self._inline_disposition(filename)
            )
            params["ResponseContentDisposition"] = disposition

        try:
            url = await asyncio.to_thread(
                self.presigned_client.generate_presigned_url,
                operation.value,
                Params=params,
                ExpiresIn=expires_in,
            )
        except ClientError as exc:
            raise self._map_client_error(exc, operation="presign") from exc
        self.logger.info("Generated presigned URL for object '%s' with expiry %s seconds.", normalized_key, expires_in)
        return StoragePresignedUrlResponse(
            object_key=normalized_key,
            url=url,
            http_method="PUT" if operation is StoragePresignedOperation.UPLOAD else "GET",
            expires_in=expires_in,
            headers=required_headers,
        )

    async def generate_presigned_upload(
        self,
        filename: str,
        content_type: str,
        file_size: int,
        prefix: str = "uploads",
        expiry: int | None = None,
    ) -> StoragePresignedUrlResponse:
        if not filename or not filename.strip():
            raise StorageValidationError(message="A filename is required for uploads.")
        object_key = self._object_key_for(filename, prefix=prefix)
        return await self.generate_presigned_url(
            object_key=object_key,
            operation=StoragePresignedOperation.UPLOAD,
            expiry=expiry,
            content_type=content_type,
            file_size=file_size,
        )

    async def generate_presigned_download(
        self,
        file_id_or_key: str,
        expiry: int | None = None,
        content_disposition: str = "attachment",
    ) -> StoragePresignedUrlResponse:
        """Convenience method to generate a presigned download URL resolving file_id or exact key."""
        try:
            key = await asyncio.to_thread(self._sync_resolve_key, file_id_or_key)
        except Exception:
            key = file_id_or_key
        return await self.generate_presigned_url(
            object_key=key,
            operation=StoragePresignedOperation.DOWNLOAD,
            expiry=expiry,
            content_disposition=content_disposition,
        )

    async def generate_presigned_urls(
        self,
        filename: str,
        content_type: str = "application/octet-stream",
        expires_in: int | None = None,
        prefix: str = "uploads",
        file_size: int | None = None,
    ) -> PresignedUrlsResponse:
        """
        Generate both an upload presigned URL (PUT) and a download presigned URL (GET)
        for an object in a single request, matching the Bruno workflow.
        """
        if not filename or not filename.strip():
            raise StorageValidationError(message="A filename is required for uploads.")

        file_id = str(uuid.uuid4())
        clean_name = Path(filename.strip()).name or "file"
        clean_prefix = (prefix or "uploads").strip().strip("/")
        key = f"{clean_prefix}/{file_id}/{clean_name}"

        expiry_duration = expires_in if (expires_in is not None and expires_in > 0) else int(self.settings.PRESIGNED_URL_EXPIRE_SECONDS)
        ctype = content_type or "application/octet-stream"

        if file_size is not None and file_size > 0:
            self._validate_file_size(file_size)

        # Upload presigned URL (PUT)
        upload_params: dict[str, Any] = {
            "Bucket": self.bucket_name,
            "Key": key,
            "ContentType": ctype,
        }
        try:
            upload_url = await asyncio.to_thread(
                self.presigned_client.generate_presigned_url,
                "put_object",
                Params=upload_params,
                ExpiresIn=expiry_duration,
            )
        except ClientError as exc:
            raise self._map_client_error(exc, operation="upload_presign") from exc

        # Download presigned URL (GET)
        download_params: dict[str, Any] = {
            "Bucket": self.bucket_name,
            "Key": key,
        }
        try:
            download_url = await asyncio.to_thread(
                self.presigned_client.generate_presigned_url,
                "get_object",
                Params=download_params,
                ExpiresIn=expiry_duration,
            )
        except ClientError as exc:
            raise self._map_client_error(exc, operation="download_presign") from exc

        self.logger.info(
            "Generated upload and download presigned URLs for object '%s' with expiry %s seconds.",
            key,
            expiry_duration,
        )

        return PresignedUrlsResponse(
            file_id=file_id,
            key=key,
            filename=clean_name,
            content_type=ctype,
            upload_url=upload_url,
            download_url=download_url,
            expires_in=expiry_duration,
        )


    async def file_exists(self, object_key: str) -> bool:
        normalized_key = self._normalize_object_key(object_key)
        try:
            await asyncio.to_thread(self.client.head_object, Bucket=self.bucket_name, Key=normalized_key)
            return True
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code")
            if error_code in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise self._map_client_error(exc, operation="exists") from exc

    def _normalize_object_key(self, object_key: str) -> str:
        normalized = (object_key or "").strip()
        if not normalized:
            raise StorageValidationError(message="Object key cannot be empty.")
        if normalized.startswith("/"):
            normalized = normalized.lstrip("/")
        if not normalized:
            raise StorageValidationError(message="Object key cannot be empty.")
        return normalized

    def _validate_file_size(self, file_size: int) -> None:
        if file_size is None or file_size <= 0:
            raise StorageValidationError(message="A positive file size is required for uploads.")
        max_size = getattr(self.settings, "MAX_UPLOAD_SIZE_BYTES", 50 * 1024 * 1024)
        if file_size > max_size:
            raise StorageValidationError(
                message=f"File size {file_size} exceeds maximum permitted upload limit ({max_size} bytes)."
            )

    def _validate_allowed_content_type(self, content_type: str) -> None:
        if not content_type or not content_type.strip():
            raise StorageValidationError(message="Missing content type for upload validation.")
        allowed = getattr(self.settings, "ALLOWED_UPLOAD_CONTENT_TYPES", None)
        if allowed:
            allowed_set = {ct.lower() for ct in allowed}
            if content_type.lower() not in allowed_set:
                raise StorageValidationError(
                    message=f"Content type '{content_type}' is not allowed for uploads."
                )

    def _inline_disposition(self, filename: str) -> str:
        clean = (filename or "file").replace('"', "").replace("\r", "").replace("\n", "")
        return f'inline; filename="{clean}"'

    def _attachment_disposition(self, filename: str) -> str:
        clean = (filename or "file").replace('"', "").replace("\r", "").replace("\n", "")
        return f'attachment; filename="{clean}"'

    def _object_key_for(self, filename: str, prefix: str = "uploads") -> str:
        clean_name = Path(filename).name or "file"
        file_id = str(uuid.uuid4())
        clean_prefix = (prefix or self.default_prefix).strip("/")
        return f"{clean_prefix}/{file_id}/{clean_name}"

    def _map_client_error(self, exc: ClientError, operation: str) -> StorageError:
        error = exc.response.get("Error", {})
        code = str(error.get("Code") or "ClientError")
        message = str(error.get("Message") or str(exc))

        if code in {"NoSuchKey", "NotFound", "404"}:
            return FileNotFoundError(message=f"File not found while {operation}: {message}")
        if code in {"NoSuchBucket", "BucketNotFound"}:
            return BucketNotFoundError(message=f"Storage bucket '{self.bucket_name}' was not found while {operation}.")
        if code in {"AccessDenied", "403", "Forbidden"}:
            return StoragePermissionDenied(message=f"Access denied while {operation}: {message}")
        if code == "InvalidObjectState":
            return StorageError(message=f"The file object has an invalid state while {operation}: {message}")
        if code in {"InvalidAccessKeyId", "SignatureDoesNotMatch"}:
            return StoragePermissionDenied(message="S3 credentials are invalid or expired.")
        return UploadFailedError(message=f"S3 request failed while {operation}: {message}") if operation == "upload" else StorageError(message=f"S3 request failed while {operation}: {message}")

    async def close(self) -> None:
        """Close the underlying boto3 client gracefully."""
        clients = (self.client, self.presigned_client)
        for index, client in enumerate(clients):
            if index == 1 and client is self.client:
                continue
            if hasattr(client, "close"):
                client.close()
