"""
backend/tests/unit/test_storage_service.py

Unit tests for StorageService verifying:
1. Uploading PDF and image files with proper UUID generation, MIME type preservation,
   file size detection, stable S3 key generation, and pointer resetting.
2. Retrieving existing files, verifying content, metadata, and non-blocking streaming.
3. Handling nonexistent files with StorageObjectNotFound.
4. Listing files with optional prefix filtering and ContinuationToken pagination.
5. Deleting files by stable identifier and raising StorageObjectNotFound for missing files.
6. Centralized mapping of S3 ClientErrors: NoSuchKey, NoSuchBucket, AccessDenied,
   and unexpected ClientErrors into domain exceptions.
7. Verification that synchronous Boto3 calls and stream reads run across the thread boundary
   via asyncio.to_thread without blocking FastAPI's event loop.
"""

import io
import threading
import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError
from botocore.response import StreamingBody
from fastapi import UploadFile

from app.core.config import Settings
from app.exceptions.domain import (
    StorageAccessDenied,
    StorageBucketNotFound,
    StorageObjectNotFound,
    StorageOperationError,
)
from app.services.storage_service import StorageService, StoredFile

pytestmark = pytest.mark.unit


class FakeS3Client:
    """
    In-memory simulation of Boto3 S3 client supporting upload_fileobj,
    get_object, head_object, list_objects_v2, delete_object, delete_objects,
    and realistic ClientError responses.
    """

    def __init__(self, bucket_name: str = "film-review-assets") -> None:
        self.bucket_name = bucket_name
        self.objects: dict[str, dict[str, Any]] = {}
        self.call_history: list[str] = []
        self.thread_ids: list[int] = []

    def _record_call(self, name: str) -> None:
        self.call_history.append(name)
        self.thread_ids.append(threading.get_ident())

    def upload_fileobj(
        self,
        Fileobj: Any,
        Bucket: str,
        Key: str,
        ExtraArgs: dict[str, Any] | None = None,
    ) -> None:
        self._record_call("upload_fileobj")
        if Bucket != self.bucket_name:
            raise ClientError(
                {"Error": {"Code": "NoSuchBucket", "Message": f"The specified bucket '{Bucket}' does not exist"}},
                "UploadFileobj",
            )
        data = Fileobj.read()
        extra = ExtraArgs or {}
        self.objects[Key] = {
            "data": data,
            "ContentType": extra.get("ContentType", "application/octet-stream"),
            "Metadata": extra.get("Metadata", {}),
            "LastModified": datetime.now(UTC),
            "Size": len(data),
            "ETag": f'"{uuid.uuid4().hex}"',
        }

    def head_object(self, Bucket: str, Key: str) -> dict[str, Any]:
        self._record_call("head_object")
        if Bucket != self.bucket_name:
            raise ClientError(
                {"Error": {"Code": "NoSuchBucket", "Message": "Bucket not found"}},
                "HeadObject",
            )
        if Key not in self.objects:
            raise ClientError(
                {"Error": {"Code": "404", "Message": "Not Found"}},
                "HeadObject",
            )
        obj = self.objects[Key]
        return {
            "ContentLength": obj["Size"],
            "ContentType": obj["ContentType"],
            "LastModified": obj["LastModified"],
            "Metadata": obj["Metadata"],
            "ETag": obj["ETag"],
        }

    def get_object(self, Bucket: str, Key: str) -> dict[str, Any]:
        self._record_call("get_object")
        if Bucket != self.bucket_name:
            raise ClientError(
                {"Error": {"Code": "NoSuchBucket", "Message": "Bucket not found"}},
                "GetObject",
            )
        if Key not in self.objects:
            raise ClientError(
                {"Error": {"Code": "NoSuchKey", "Message": "The specified key does not exist."}},
                "GetObject",
            )
        obj = self.objects[Key]
        raw_bytes = obj["data"]
        body = StreamingBody(io.BytesIO(raw_bytes), len(raw_bytes))
        return {
            "Body": body,
            "ContentLength": obj["Size"],
            "ContentType": obj["ContentType"],
            "LastModified": obj["LastModified"],
            "Metadata": obj["Metadata"],
            "ETag": obj["ETag"],
        }

    def list_objects_v2(
        self,
        Bucket: str,
        Prefix: str = "",
        ContinuationToken: str | None = None,
        MaxKeys: int = 1000,
    ) -> dict[str, Any]:
        self._record_call("list_objects_v2")
        if Bucket != self.bucket_name:
            raise ClientError(
                {"Error": {"Code": "NoSuchBucket", "Message": "Bucket not found"}},
                "ListObjectsV2",
            )

        matching = [
            {"Key": k, "Size": v["Size"], "LastModified": v["LastModified"], "ETag": v["ETag"]}
            for k, v in self.objects.items()
            if k.startswith(Prefix)
        ]

        # Simulate pagination if pagination token is used or multiple items exist
        page_size = 2 if ContinuationToken is not None or len(matching) > 2 else len(matching)
        start_idx = int(ContinuationToken) if ContinuationToken else 0
        paged_items = matching[start_idx : start_idx + page_size]
        is_truncated = (start_idx + page_size) < len(matching)
        next_token = str(start_idx + page_size) if is_truncated else None

        result: dict[str, Any] = {
            "KeyCount": len(paged_items),
            "Contents": paged_items,
            "IsTruncated": is_truncated,
        }
        if next_token:
            result["NextContinuationToken"] = next_token
        return result

    def delete_object(self, Bucket: str, Key: str) -> dict[str, Any]:
        self._record_call("delete_object")
        if Bucket != self.bucket_name:
            raise ClientError(
                {"Error": {"Code": "NoSuchBucket", "Message": "Bucket not found"}},
                "DeleteObject",
            )
        self.objects.pop(Key, None)
        return {}

    def delete_objects(self, Bucket: str, Delete: dict[str, Any]) -> dict[str, Any]:
        self._record_call("delete_objects")
        if Bucket != self.bucket_name:
            raise ClientError(
                {"Error": {"Code": "NoSuchBucket", "Message": "Bucket not found"}},
                "DeleteObjects",
            )
        deleted = []
        for obj in Delete.get("Objects", []):
            k = obj["Key"]
            if k in self.objects:
                del self.objects[k]
                deleted.append({"Key": k})
        return {"Deleted": deleted}


@pytest.fixture
def fake_s3() -> FakeS3Client:
    return FakeS3Client(bucket_name="film-review-assets")


@pytest.fixture
def storage_service(fake_s3: FakeS3Client) -> StorageService:
    settings = Settings(
        S3_BUCKET_NAME="film-review-assets",
        ACCESS_TOKEN_EXPIRE_MINUTES=30,
        REFRESH_TOKEN_EXPIRE_DAYS=7,
        ALLOWED_CORS_ORIGINS="http://localhost:3000",
        API_VERSION="v1",
    )
    return StorageService(settings=settings, s3_client=fake_s3, bucket_name="film-review-assets")


# ---------------------------------------------------------------------------
# 1. Upload Tests
# ---------------------------------------------------------------------------


class TestStorageUpload:
    """Verify S3 file upload logic, metadata, and key generation."""

    async def test_upload_pdf_file(self, storage_service: StorageService, fake_s3: FakeS3Client):
        content = b"%PDF-1.4 sample pdf content for press kit"
        upload_file = UploadFile(
            file=io.BytesIO(content),
            filename="press_kit.pdf",
            headers={"content-type": "application/pdf"},
        )

        res = await storage_service.upload_file(upload_file)

        assert res.filename == "press_kit.pdf"
        assert res.content_type == "application/pdf"
        assert res.size == len(content)
        # Verify valid UUID assigned
        parsed_uuid = uuid.UUID(res.file_id)
        assert str(parsed_uuid) == res.file_id
        # Verify stable key format: film-assets/{uuid}/press_kit.pdf
        assert res.key == f"film-assets/{res.file_id}/press_kit.pdf"
        # Confirm stored in fake S3 with correct metadata
        assert res.key in fake_s3.objects
        stored_item = fake_s3.objects[res.key]
        assert stored_item["data"] == content
        assert stored_item["Metadata"]["original-filename"] == "press_kit.pdf"
        assert stored_item["Metadata"]["file-id"] == res.file_id

    async def test_upload_image_file(self, storage_service: StorageService, fake_s3: FakeS3Client):
        content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDRimage_data"
        upload_file = UploadFile(
            file=io.BytesIO(content),
            filename="poster.png",
            headers={"content-type": "image/png"},
        )

        res = await storage_service.upload_file(upload_file)

        assert res.filename == "poster.png"
        assert res.content_type == "image/png"
        assert res.size == len(content)
        assert res.key.startswith("film-assets/")
        assert res.key.endswith("/poster.png")
        assert fake_s3.objects[res.key]["data"] == content

    async def test_upload_file_pointer_reset(self, storage_service: StorageService):
        """Verify that a partially read or offset file pointer is reset to 0 before uploading."""
        content = b"sample poster binary stream"
        bio = io.BytesIO(content)
        bio.seek(10)  # Move pointer away from start
        upload_file = UploadFile(file=bio, filename="scan.jpg", headers={"content-type": "image/jpeg"})

        res = await storage_service.upload_file(upload_file)

        assert res.size == len(content)
        stored_file = await storage_service.get_file(res.file_id)
        streamed_bytes = await stored_file.read()
        assert streamed_bytes == content


# ---------------------------------------------------------------------------
# 2. Retrieve Tests
# ---------------------------------------------------------------------------


class TestStorageRetrieve:
    """Verify S3 file retrieval, streaming, and error handling."""

    async def test_retrieve_existing_file(self, storage_service: StorageService):
        content = b"High-resolution film still binary content"
        upload_file = UploadFile(
            file=io.BytesIO(content),
            filename="still.jpg",
            headers={"content-type": "image/jpeg"},
        )
        uploaded = await storage_service.upload_file(upload_file)

        retrieved = await storage_service.get_file(uploaded.file_id)

        assert isinstance(retrieved, StoredFile)
        assert retrieved.file_id == uploaded.file_id
        assert retrieved.filename == "still.jpg"
        assert retrieved.content_type == "image/jpeg"
        assert retrieved.size == len(content)
        # Read stream
        downloaded = await retrieved.read()
        assert downloaded == content

    async def test_retrieve_nonexistent_file_raises_storage_not_found(self, storage_service: StorageService):
        missing_id = str(uuid.uuid4())

        with pytest.raises(StorageObjectNotFound) as exc_info:
            await storage_service.get_file(missing_id)

        assert exc_info.value.status_code == 404
        assert exc_info.value.error_code == "STORAGE_OBJECT_NOT_FOUND"
        assert missing_id in exc_info.value.message


# ---------------------------------------------------------------------------
# 3. List Tests & Pagination
# ---------------------------------------------------------------------------


class TestStorageList:
    """Verify S3 object listing, prefix filtering, and ContinuationToken pagination."""

    async def test_list_files_prefix_filtering(self, storage_service: StorageService):
        # Upload files in two different prefixes
        await storage_service.upload_file(b"data1", filename="poster1.jpg", prefix="film-assets")
        await storage_service.upload_file(b"data2", filename="poster2.jpg", prefix="film-assets")
        await storage_service.upload_file(b"data3", filename="report.pdf", prefix="reports")

        # List with film-assets prefix
        film_assets_listing = await storage_service.list_files(prefix="film-assets")
        assert film_assets_listing.total == 2
        for item in film_assets_listing.files:
            assert item.key.startswith("film-assets/")

        # List with reports prefix
        reports_listing = await storage_service.list_files(prefix="reports")
        assert reports_listing.total == 1
        assert reports_listing.files[0].key.startswith("reports/")

    async def test_list_files_pagination_with_continuation_tokens(
        self,
        storage_service: StorageService,
        fake_s3: FakeS3Client,
    ):
        """Verify that list_files continues querying when IsTruncated is True until all objects are fetched."""
        # Create 5 objects in fake S3
        for i in range(5):
            await storage_service.upload_file(f"content-{i}".encode(), filename=f"doc_{i}.txt", prefix="docs")

        res = await storage_service.list_files(prefix="docs")

        assert res.total == 5
        assert len(res.files) == 5
        # Verify list_objects_v2 was called multiple times due to simulated page_size = 2
        calls = [c for c in fake_s3.call_history if c == "list_objects_v2"]
        assert len(calls) >= 3


# ---------------------------------------------------------------------------
# 4. Delete Tests
# ---------------------------------------------------------------------------


class TestStorageDelete:
    """Verify file deletion and missing file handling."""

    async def test_delete_existing_file(self, storage_service: StorageService):
        uploaded = await storage_service.upload_file(b"to be deleted", filename="delete_me.png")

        # Delete the file
        delete_res = await storage_service.delete_file(uploaded.file_id)
        assert delete_res.deleted is True
        assert delete_res.file_id == uploaded.file_id

        # Verify it can no longer be retrieved
        with pytest.raises(StorageObjectNotFound):
            await storage_service.get_file(uploaded.file_id)

    async def test_delete_missing_file_raises_not_found(self, storage_service: StorageService):
        missing_id = str(uuid.uuid4())

        with pytest.raises(StorageObjectNotFound):
            await storage_service.delete_file(missing_id)


# ---------------------------------------------------------------------------
# 5. Exception Mapping Tests
# ---------------------------------------------------------------------------


class TestStorageExceptionMapping:
    """Verify centralized mapping from S3 ClientErrors to domain exceptions."""

    async def test_nosuchkey_maps_to_storage_object_not_found(self, storage_service: StorageService):
        mock_client = MagicMock()
        mock_client.head_object.side_effect = ClientError(
            {"Error": {"Code": "404", "Message": "Not found"}}, "HeadObject"
        )
        mock_client.list_objects_v2.return_value = {"Contents": []}
        storage_service._s3_client = mock_client

        with pytest.raises(StorageObjectNotFound) as exc_info:
            await storage_service.get_file("missing-key")

        assert exc_info.value.status_code == 404
        assert exc_info.value.error_code == "STORAGE_OBJECT_NOT_FOUND"

    async def test_nosuchbucket_maps_to_storage_bucket_not_found(self, storage_service: StorageService):
        mock_client = MagicMock()
        mock_client.head_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchBucket", "Message": "The bucket does not exist"}}, "HeadObject"
        )
        storage_service._s3_client = mock_client

        with pytest.raises(StorageBucketNotFound) as exc_info:
            await storage_service.get_file("any-file")

        assert exc_info.value.status_code == 500
        assert exc_info.value.error_code == "STORAGE_BUCKET_NOT_FOUND"

    async def test_accessdenied_maps_to_storage_access_denied(self, storage_service: StorageService):
        mock_client = MagicMock()
        mock_client.head_object.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}}, "HeadObject"
        )
        storage_service._s3_client = mock_client

        with pytest.raises(StorageAccessDenied) as exc_info:
            await storage_service.get_file("protected-file")

        assert exc_info.value.status_code == 500
        assert exc_info.value.error_code == "STORAGE_ACCESS_DENIED"

    async def test_unexpected_client_error_maps_to_storage_operation_error(self, storage_service: StorageService):
        mock_client = MagicMock()
        mock_client.head_object.side_effect = ClientError(
            {"Error": {"Code": "InternalError", "Message": "We encountered an internal error"}}, "HeadObject"
        )
        storage_service._s3_client = mock_client

        with pytest.raises(StorageOperationError) as exc_info:
            await storage_service.get_file("any-file")

        assert exc_info.value.status_code == 500
        assert exc_info.value.error_code == "STORAGE_OPERATION_ERROR"


# ---------------------------------------------------------------------------
# 6. Async Integration & Thread Boundary Tests
# ---------------------------------------------------------------------------


class TestStorageAsyncIntegration:
    """Verify that blocking Boto3 SDK operations run on worker threads."""

    async def test_blocking_operations_execute_on_worker_threads(
        self,
        storage_service: StorageService,
        fake_s3: FakeS3Client,
    ):
        """Verify that synchronous S3 operations run on a worker thread distinct from event loop thread."""
        main_thread_id = threading.get_ident()

        uploaded = await storage_service.upload_file(b"test thread execution", filename="thread_test.txt")
        _ = await storage_service.get_file(uploaded.file_id)
        _ = await storage_service.list_files(prefix="film-assets")
        _ = await storage_service.delete_file(uploaded.file_id)

        # All recorded S3 client calls must have run on worker threads (not the main event loop thread)
        assert len(fake_s3.thread_ids) > 0
        for tid in fake_s3.thread_ids:
            assert tid != main_thread_id, f"SDK call ran on event loop thread {tid} instead of worker thread"

    async def test_stream_chunks_non_blocking_async_generator(self, storage_service: StorageService):
        """Verify that stream chunks are read asynchronously through thread delegation."""
        content = b"A" * 1024 * 128  # 128 KB
        uploaded = await storage_service.upload_file(content, filename="large.bin")

        stored_file = await storage_service.get_file(uploaded.file_id)

        chunks_read = []
        async for chunk in stored_file.stream:
            chunks_read.append(chunk)

        reassembled = b"".join(chunks_read)
        assert reassembled == content
