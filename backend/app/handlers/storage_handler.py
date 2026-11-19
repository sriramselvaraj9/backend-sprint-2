from fastapi import UploadFile

from app.schemas.storage import (
    FileDeleteResponse,
    FileListResponse,
    FileUploadResponse,
    PresignedUrlsResponse,
    StoragePresignedOperation,
    StoragePresignedUrlResponse,
)
from app.services.storage_service import StorageService, StoredFile


class StorageHandler:
    """
    Handler layer for file storage operations.
    Coordinates between HTTP route definitions and the StorageService layer.
    Contains NO direct S3 SDK calls.
    """

    def __init__(self, service: StorageService) -> None:
        self.service = service

    async def upload_file(self, file: UploadFile) -> FileUploadResponse:
        """Process and delegate file upload to StorageService."""
        return await self.service.upload_file(file=file)

    async def get_file(self, file_id: str) -> StoredFile:
        """Retrieve stored file and stream wrapper from StorageService."""
        return await self.service.get_file(file_id=file_id)

    async def list_files(
        self,
        prefix: str | None = None,
        max_keys: int | None = None,
        continuation_token: str | None = None,
    ) -> FileListResponse:
        """Retrieve stored files list from StorageService."""
        return await self.service.list_files(
            prefix=prefix,
            max_keys=max_keys,
            continuation_token=continuation_token,
        )

    async def delete_file(self, file_id: str) -> FileDeleteResponse:
        """Delete stored file through StorageService."""
        return await self.service.delete_file(file_id=file_id)

    async def generate_presigned_url(
        self,
        object_key: str,
        operation: StoragePresignedOperation = StoragePresignedOperation.DOWNLOAD,
        expiry: int | None = None,
        content_type: str | None = None,
        file_size: int | None = None,
        content_disposition: str = "attachment",
    ) -> StoragePresignedUrlResponse:
        """Generate a presigned S3 URL for upload or download."""
        return await self.service.generate_presigned_url(
            object_key=object_key,
            operation=operation,
            expiry=expiry,
            content_type=content_type,
            file_size=file_size,
            content_disposition=content_disposition,
        )

    async def generate_presigned_upload(
        self,
        filename: str,
        content_type: str,
        file_size: int,
        prefix: str = "uploads",
        expiry: int | None = None,
    ) -> StoragePresignedUrlResponse:
        """Generate a presigned PUT URL for direct client-to-S3 upload."""
        return await self.service.generate_presigned_upload(
            filename=filename,
            content_type=content_type,
            file_size=file_size,
            prefix=prefix,
            expiry=expiry,
        )

    async def generate_presigned_download(
        self,
        file_id_or_key: str,
        expiry: int | None = None,
        content_disposition: str = "attachment",
    ) -> StoragePresignedUrlResponse:
        """Generate a presigned GET URL for temporary direct-from-S3 download."""
        return await self.service.generate_presigned_download(
            file_id_or_key=file_id_or_key,
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
        """Generate paired upload (PUT) and download (GET) presigned URLs."""
        return await self.service.generate_presigned_urls(
            filename=filename,
            content_type=content_type,
            expires_in=expires_in,
            prefix=prefix,
            file_size=file_size,
        )

    async def file_exists(self, object_key: str) -> bool:
        """Check whether an S3 object key exists via HEAD request."""
        return await self.service.file_exists(object_key=object_key)


