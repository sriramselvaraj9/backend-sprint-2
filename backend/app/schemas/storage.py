from datetime import datetime
from enum import Enum

from typing import Any
from pydantic import Field, field_validator

from app.schemas.common import BaseSchema


class StoragePresignedOperation(str, Enum):
    """Supported S3 presigned operations."""

    UPLOAD = "put_object"
    DOWNLOAD = "get_object"


class StoragePresignedUrlResponse(BaseSchema):
    """Schema returned when an S3 presigned URL is generated."""

    object_key: str = Field(..., description="Normalized S3 object key")
    url: str = Field(..., description="Cryptographically signed temporary S3 presigned URL")
    http_method: str = Field(..., description="Permitted HTTP method (PUT for upload, GET for download)")
    expires_in: int = Field(..., ge=1, description="URL validity duration in seconds")
    headers: dict[str, str] = Field(default_factory=dict, description="Required HTTP request headers to include")


class PresignedUrlsRequest(BaseSchema):
    """Request payload for generating paired upload and download presigned URLs."""

    filename: str = Field(..., min_length=1, description="Filename for the upload target")
    content_type: str = Field(default="application/octet-stream", description="MIME content type of the file")
    expires_in: int | None = Field(default=None, description="Expiry duration in seconds")
    expiry: int | None = Field(default=None, description="Alternative alias for expires_in")
    prefix: str | None = Field(default="uploads", description="Target S3 key prefix")
    file_size: int | None = Field(default=None, description="Optional expected file size in bytes")

    @field_validator("expires_in", "expiry", mode="before")
    @classmethod
    def parse_empty_or_int(cls, v: Any) -> int | None:
        if v is None or v == "":
            return None
        return int(v)

    @field_validator("prefix", mode="before")
    @classmethod
    def parse_prefix(cls, v: Any) -> str:
        if not v or not str(v).strip():
            return "uploads"
        return str(v).strip()

    @field_validator("file_size", mode="before")
    @classmethod
    def parse_file_size(cls, v: Any) -> int | None:
        if v is None or v == "":
            return None
        return int(v)


class PresignedUrlsResponse(BaseSchema):
    """Response containing both upload (PUT) and download (GET) presigned URLs."""

    file_id: str = Field(..., description="Stable unique identifier for the stored file")
    key: str = Field(..., description="Full S3 object key")
    filename: str = Field(..., description="Original filename of the file")
    content_type: str = Field(..., description="MIME content type of the file")
    upload_url: str = Field(..., description="Presigned PUT URL for uploading to S3")
    download_url: str = Field(..., description="Presigned GET URL for downloading/viewing from S3")
    expires_in: int = Field(..., ge=1, description="URL validity duration in seconds")


class PresignedUploadRequest(BaseSchema):
    """Request payload for generating a presigned upload URL."""

    filename: str = Field(..., min_length=1, description="Filename for the upload target")
    content_type: str = Field(default="application/octet-stream", description="MIME content type of the file")
    file_size: int | None = Field(default=None, description="Size of the file in bytes")
    prefix: str | None = Field(default="uploads", description="Target S3 key prefix")
    expiry: int | None = Field(default=None, description="Optional custom expiry in seconds")
    expires_in: int | None = Field(default=None, description="Optional custom expiry in seconds")

    @field_validator("expiry", "expires_in", mode="before")
    @classmethod
    def parse_empty_or_int_expiry(cls, v: Any) -> int | None:
        if v is None or v == "":
            return None
        return int(v)

    @field_validator("prefix", mode="before")
    @classmethod
    def parse_upload_prefix(cls, v: Any) -> str:
        if not v or not str(v).strip():
            return "uploads"
        return str(v).strip()

    @field_validator("file_size", mode="before")
    @classmethod
    def parse_upload_file_size(cls, v: Any) -> int | None:
        if v is None or v == "":
            return None
        return int(v)



class PresignedDownloadRequest(BaseSchema):
    """Request query/payload for generating a presigned download URL."""

    object_key: str = Field(..., min_length=1, description="S3 object key to download")
    content_disposition: str = Field(default="attachment", description="'attachment' or 'inline'")
    expiry: int | None = Field(default=None, ge=1, le=604800, description="Optional custom expiry in seconds")


class FileUploadResponse(BaseSchema):
    """Schema returned after a file is successfully uploaded to S3."""

    file_id: str = Field(..., description="Stable unique identifier for the stored file")
    filename: str = Field(..., description="Original filename of the uploaded file")
    content_type: str = Field(..., description="MIME content type of the file")
    size: int = Field(..., ge=0, description="Size of the file in bytes")
    key: str = Field(..., description="Full S3 object key")
    uploaded_at: datetime = Field(..., description="Timestamp of upload")


class FileListItem(BaseSchema):
    """Schema representing an individual stored file in a listing."""

    key: str = Field(..., description="Full S3 object key")
    size: int = Field(..., ge=0, description="Size of the object in bytes")
    last_modified: datetime = Field(..., description="Last modified timestamp from S3")
    etag: str | None = Field(default=None, description="Entity tag / hash of the object")


class FileListResponse(BaseSchema):
    """Schema returned when listing stored files with optional prefix and pagination."""

    files: list[FileListItem] = Field(default_factory=list, description="Matching stored objects")
    total: int = Field(..., ge=0, description="Total count of matching files")
    prefix: str | None = Field(default=None, description="Applied search prefix filter, if any")
    next_continuation_token: str | None = Field(default=None, description="Continuation token for the next page of results")
    is_truncated: bool = Field(default=False, description="Indicates if additional matching files remain")


class FileDeleteResponse(BaseSchema):
    """Schema returned after a file is successfully deleted from S3."""

    file_id: str = Field(..., description="Identifier of the deleted file")
    key: str = Field(..., description="Object key that was deleted from S3")
    deleted: bool = Field(default=True, description="Deletion confirmation indicator")
    message: str = Field(..., description="Descriptive status message")
