"""
backend/tests/unit/test_presigned_urls.py

Comprehensive unit tests for S3 Presigned URL implementation verifying:
1. Generating presigned upload URL (PUT method, required headers, expiry, key generation).
2. Generating presigned download URL (GET method, attachment and inline content-disposition, expiry).
3. Upload parameter validation (missing content type, non-positive file size, size limits, disallowed content types).
4. Download parameter validation (disallowed content_disposition).
5. Object key normalization (trimming whitespace, stripping leading slashes, reject empty keys).
6. File existence checks via S3 HEAD request (True on 200, False on 404/NoSuchKey, error mapping).
7. S3 ClientError mapping into typed domain exceptions (NoSuchKey -> FileNotFoundError, NoSuchBucket -> BucketNotFoundError,
   AccessDenied -> StoragePermissionDenied, InvalidAccessKeyId -> StoragePermissionDenied, InvalidObjectState -> StorageError).
8. Graceful closure of underlying S3 and presigned clients.
9. Security boundary verification (temporary public access without leaking AWS IAM credentials).
"""

import asyncio
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

import app.core.secrets as _secrets_mod
from app.core.secrets import AppSecrets, DatabaseSecret, JWTSecret

# Populate test secret cache prior to importing app modules so Settings() can initialize offline
if _secrets_mod._cached_secrets is None:
    _secrets_mod._cached_secrets = AppSecrets(
        database=DatabaseSecret(
            username="postgres",
            password="password",
            host="localhost",
            port=5432,
            database="film_review_db",
        ),
        jwt=JWTSecret(secret_key="test-jwt-secret-key-12345"),
    )

from app.core.config import Settings
from app.exceptions.domain import (
    BucketNotFoundError,
    FileNotFoundError,
    StorageError,
    StoragePermissionDenied,
    StorageValidationError,
    UploadFailedError,
)
from app.schemas.storage import (
    StoragePresignedOperation,
    StoragePresignedUrlResponse,
)
from app.services.storage_service import StorageService

pytestmark = pytest.mark.unit


def run_coro(coro):
    """
    Drive a coroutine to completion synchronously.
    Avoids ProactorEventLoop loopback socketpair creation on Windows sandbox.
    """
    try:
        coro.send(None)
    except StopIteration as exc:
        return exc.value


@pytest.fixture(autouse=True)
def mock_asyncio_to_thread(monkeypatch):
    """Mock asyncio.to_thread to execute synchronously within coroutine execution."""
    async def _to_thread(func, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr(asyncio, "to_thread", _to_thread)


@pytest.fixture
def mock_s3_client():
    client = MagicMock()
    client.generate_presigned_url.return_value = "https://film-review-assets.s3.amazonaws.com/uploads/fake-signed-url"
    client.head_object.return_value = {"ContentLength": 1024, "ContentType": "image/jpeg"}
    return client


@pytest.fixture
def storage_service(mock_s3_client):
    settings = Settings(
        S3_BUCKET_NAME="film-review-assets",
        S3_DEFAULT_PREFIX="film-assets",
        PRESIGNED_URL_EXPIRE_SECONDS=900,
        MAX_UPLOAD_SIZE_BYTES=50 * 1024 * 1024,
        ALLOWED_UPLOAD_CONTENT_TYPES=["image/jpeg", "image/png", "application/pdf"],
        ACCESS_TOKEN_EXPIRE_MINUTES=30,
        REFRESH_TOKEN_EXPIRE_DAYS=7,
        ALLOWED_CORS_ORIGINS="http://localhost:3000",
        API_VERSION="v1",
    )
    return StorageService(settings=settings, s3_client=mock_s3_client, presigned_client=mock_s3_client)


# ===========================================================================
# 1. Key Normalization Tests
# ===========================================================================

class TestKeyNormalization:
    def test_normalize_valid_key(self, storage_service: StorageService):
        assert storage_service._normalize_object_key("uploads/photo.jpg") == "uploads/photo.jpg"
        assert storage_service._normalize_object_key("/leading/slash.png") == "leading/slash.png"
        assert storage_service._normalize_object_key("///multiple/slashes.pdf") == "multiple/slashes.pdf"
        assert storage_service._normalize_object_key("   padded/spaces.pdf   ") == "padded/spaces.pdf"

    def test_normalize_empty_key_raises(self, storage_service: StorageService):
        with pytest.raises(StorageValidationError, match="Object key cannot be empty"):
            storage_service._normalize_object_key("")

        with pytest.raises(StorageValidationError, match="Object key cannot be empty"):
            storage_service._normalize_object_key("   ")

        with pytest.raises(StorageValidationError, match="Object key cannot be empty"):
            storage_service._normalize_object_key("///")


# ===========================================================================
# 2. Presigned Upload URL Tests
# ===========================================================================

class TestPresignedUpload:
    def test_generate_presigned_upload_success(self, storage_service: StorageService, mock_s3_client: MagicMock):
        res: StoragePresignedUrlResponse = run_coro(
            storage_service.generate_presigned_upload(
                filename="poster.jpg",
                content_type="image/jpeg",
                file_size=2048,
                prefix="uploads",
                expiry=600,
            )
        )

        assert res.http_method == "PUT"
        assert res.expires_in == 600
        assert res.url.startswith("https://")
        assert res.object_key.startswith("uploads/")
        assert res.object_key.endswith("/poster.jpg")
        assert res.headers == {
            "Content-Type": "image/jpeg",
            "Content-Disposition": 'inline; filename="poster.jpg"',
        }

        # Verify underlying boto3 generate_presigned_url call
        mock_s3_client.generate_presigned_url.assert_called_once_with(
            "put_object",
            Params={
                "Bucket": "film-review-assets",
                "Key": res.object_key,
                "ContentType": "image/jpeg",
                "ContentDisposition": 'inline; filename="poster.jpg"',
            },
            ExpiresIn=600,
        )

    def test_generate_presigned_upload_default_expiry(self, storage_service: StorageService, mock_s3_client: MagicMock):
        res = run_coro(
            storage_service.generate_presigned_upload(
                filename="document.pdf",
                content_type="application/pdf",
                file_size=5000,
            )
        )
        assert res.expires_in == 900
        mock_s3_client.generate_presigned_url.assert_called_once_with(
            "put_object",
            Params={
                "Bucket": "film-review-assets",
                "Key": res.object_key,
                "ContentType": "application/pdf",
                "ContentDisposition": 'inline; filename="document.pdf"',
            },
            ExpiresIn=900,
        )

    def test_upload_missing_filename(self, storage_service: StorageService):
        with pytest.raises(StorageValidationError, match="A filename is required for uploads"):
            run_coro(
                storage_service.generate_presigned_upload(
                    filename="",
                    content_type="image/jpeg",
                    file_size=1000,
                )
            )

    def test_upload_missing_content_type(self, storage_service: StorageService):
        with pytest.raises(StorageValidationError, match="Missing content type for upload validation"):
            run_coro(
                storage_service.generate_presigned_url(
                    object_key="uploads/test.jpg",
                    operation=StoragePresignedOperation.UPLOAD,
                    content_type="",
                    file_size=1000,
                )
            )

    def test_upload_invalid_file_size(self, storage_service: StorageService):
        with pytest.raises(StorageValidationError, match="A positive file size is required for uploads"):
            run_coro(
                storage_service.generate_presigned_url(
                    object_key="uploads/test.jpg",
                    operation=StoragePresignedOperation.UPLOAD,
                    content_type="image/jpeg",
                    file_size=0,
                )
            )

        with pytest.raises(StorageValidationError, match="A positive file size is required for uploads"):
            run_coro(
                storage_service.generate_presigned_url(
                    object_key="uploads/test.jpg",
                    operation=StoragePresignedOperation.UPLOAD,
                    content_type="image/jpeg",
                    file_size=-50,
                )
            )

    def test_upload_file_size_exceeds_limit(self, storage_service: StorageService):
        with pytest.raises(StorageValidationError, match="exceeds maximum permitted upload limit"):
            run_coro(
                storage_service.generate_presigned_url(
                    object_key="uploads/test.jpg",
                    operation=StoragePresignedOperation.UPLOAD,
                    content_type="image/jpeg",
                    file_size=60 * 1024 * 1024,  # 60MB > 50MB limit
                )
            )

    def test_upload_disallowed_content_type(self, storage_service: StorageService):
        with pytest.raises(StorageValidationError, match="is not allowed for uploads"):
            run_coro(
                storage_service.generate_presigned_url(
                    object_key="uploads/script.exe",
                    operation=StoragePresignedOperation.UPLOAD,
                    content_type="application/x-msdownload",
                    file_size=1000,
                )
            )


# ===========================================================================
# 3. Presigned Download URL Tests
# ===========================================================================

class TestPresignedDownload:
    def test_generate_presigned_download_attachment_default(
        self, storage_service: StorageService, mock_s3_client: MagicMock
    ):
        res: StoragePresignedUrlResponse = run_coro(
            storage_service.generate_presigned_url(
                object_key="film-assets/123/trailer.mp4",
                operation=StoragePresignedOperation.DOWNLOAD,
                expiry=300,
            )
        )

        assert res.http_method == "GET"
        assert res.expires_in == 300
        assert res.headers == {}
        assert res.object_key == "film-assets/123/trailer.mp4"

        mock_s3_client.generate_presigned_url.assert_called_once_with(
            "get_object",
            Params={
                "Bucket": "film-review-assets",
                "Key": "film-assets/123/trailer.mp4",
                "ResponseContentDisposition": 'attachment; filename="trailer.mp4"',
            },
            ExpiresIn=300,
        )

    def test_generate_presigned_download_inline(
        self, storage_service: StorageService, mock_s3_client: MagicMock
    ):
        res = run_coro(
            storage_service.generate_presigned_url(
                object_key="film-assets/123/poster.png",
                operation=StoragePresignedOperation.DOWNLOAD,
                content_disposition="inline",
            )
        )

        assert res.http_method == "GET"
        mock_s3_client.generate_presigned_url.assert_called_once_with(
            "get_object",
            Params={
                "Bucket": "film-review-assets",
                "Key": "film-assets/123/poster.png",
                "ResponseContentDisposition": 'inline; filename="poster.png"',
            },
            ExpiresIn=900,
        )

    def test_generate_presigned_download_invalid_disposition(self, storage_service: StorageService):
        with pytest.raises(StorageValidationError, match="content_disposition must be 'attachment' or 'inline'"):
            run_coro(
                storage_service.generate_presigned_url(
                    object_key="film-assets/123/poster.png",
                    operation=StoragePresignedOperation.DOWNLOAD,
                    content_disposition="invalid_mode",
                )
            )


# ===========================================================================
# 4. File Exists & S3 Head Object Tests
# ===========================================================================

class TestFileExists:
    def test_file_exists_true(self, storage_service: StorageService, mock_s3_client: MagicMock):
        exists = run_coro(storage_service.file_exists("uploads/existing.jpg"))
        assert exists is True
        mock_s3_client.head_object.assert_called_once_with(
            Bucket="film-review-assets", Key="uploads/existing.jpg"
        )

    def test_file_exists_false_on_404(self, storage_service: StorageService, mock_s3_client: MagicMock):
        mock_s3_client.head_object.side_effect = ClientError(
            {"Error": {"Code": "404", "Message": "Not Found"}}, "HeadObject"
        )
        exists = run_coro(storage_service.file_exists("uploads/missing.jpg"))
        assert exists is False

    def test_file_exists_false_on_nosuchkey(self, storage_service: StorageService, mock_s3_client: MagicMock):
        mock_s3_client.head_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "No such key"}}, "HeadObject"
        )
        exists = run_coro(storage_service.file_exists("uploads/missing.jpg"))
        assert exists is False

    def test_file_exists_raises_on_access_denied(self, storage_service: StorageService, mock_s3_client: MagicMock):
        mock_s3_client.head_object.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}}, "HeadObject"
        )
        with pytest.raises(StoragePermissionDenied, match="Access denied while exists"):
            run_coro(storage_service.file_exists("uploads/forbidden.jpg"))


# ===========================================================================
# 5. ClientError Mapping Tests
# ===========================================================================

class TestClientErrorMapping:
    def test_map_nosuchkey_to_file_not_found(self, storage_service: StorageService):
        err = ClientError({"Error": {"Code": "NoSuchKey", "Message": "Key not found"}}, "GetObject")
        mapped = storage_service._map_client_error(err, operation="get")
        assert isinstance(mapped, FileNotFoundError)
        assert mapped.status_code == 404
        assert mapped.error_code == "STORAGE_OBJECT_NOT_FOUND"

    def test_map_nosuchbucket_to_bucket_not_found(self, storage_service: StorageService):
        err = ClientError({"Error": {"Code": "NoSuchBucket", "Message": "Bucket does not exist"}}, "GetObject")
        mapped = storage_service._map_client_error(err, operation="get")
        assert isinstance(mapped, BucketNotFoundError)
        assert mapped.status_code == 500
        assert mapped.error_code == "STORAGE_BUCKET_NOT_FOUND"

    def test_map_access_denied_to_permission_denied(self, storage_service: StorageService):
        err = ClientError({"Error": {"Code": "AccessDenied", "Message": "Access Denied"}}, "PutObject")
        mapped = storage_service._map_client_error(err, operation="upload")
        assert isinstance(mapped, StoragePermissionDenied)
        assert mapped.status_code == 403
        assert mapped.error_code == "STORAGE_ACCESS_DENIED"

    def test_map_invalid_access_key_to_permission_denied(self, storage_service: StorageService):
        err = ClientError({"Error": {"Code": "InvalidAccessKeyId", "Message": "Key invalid"}}, "PutObject")
        mapped = storage_service._map_client_error(err, operation="upload")
        assert isinstance(mapped, StoragePermissionDenied)
        assert "credentials are invalid" in mapped.message

    def test_map_invalid_object_state(self, storage_service: StorageService):
        err = ClientError({"Error": {"Code": "InvalidObjectState", "Message": "Object in glacier"}}, "GetObject")
        mapped = storage_service._map_client_error(err, operation="get")
        assert isinstance(mapped, StorageError)

    def test_map_generic_upload_error(self, storage_service: StorageService):
        err = ClientError({"Error": {"Code": "ServiceUnavailable", "Message": "Down"}}, "PutObject")
        mapped = storage_service._map_client_error(err, operation="upload")
        assert isinstance(mapped, UploadFailedError)
        assert mapped.status_code == 500


# ===========================================================================
# 6. Graceful Client Close Tests
# ===========================================================================

class TestClientClose:
    def test_close_gracefully_invoked(self, storage_service: StorageService, mock_s3_client: MagicMock):
        mock_s3_client.close = MagicMock()
        run_coro(storage_service.close())
        mock_s3_client.close.assert_called_once()

    def test_close_distinct_clients(self, storage_service: StorageService):
        client1 = MagicMock()
        client1.close = MagicMock()
        client2 = MagicMock()
        client2.close = MagicMock()

        storage_service.client = client1
        storage_service.presigned_client = client2

        run_coro(storage_service.close())
        client1.close.assert_called_once()
        client2.close.assert_called_once()


# ===========================================================================
# 7. Security Boundary Verification Tests
# ===========================================================================

class TestSecurityBoundary:
    def test_presigned_url_does_not_leak_credentials(
        self, storage_service: StorageService, mock_s3_client: MagicMock
    ):
        """
        Verify security boundary:
        The response contains only the signed URL, method, headers, and expiry.
        AWS Secret Key, Access Key ID, and internal session tokens are NEVER returned in response.
        """
        res: StoragePresignedUrlResponse = run_coro(
            storage_service.generate_presigned_upload(
                filename="secure_upload.pdf",
                content_type="application/pdf",
                file_size=1024,
            )
        )

        response_dict = res.model_dump()
        assert "AWS_SECRET_ACCESS_KEY" not in response_dict
        assert "aws_secret_access_key" not in response_dict
        assert "AWS_ACCESS_KEY_ID" not in response_dict
        assert "aws_access_key_id" not in response_dict
        assert "credentials" not in response_dict
        # Headers contain ONLY necessary HTTP headers for upload binding
        assert set(res.headers.keys()) == {"Content-Type", "Content-Disposition"}


# ===========================================================================
# 8. Dual Presigned URLs (Upload + Download) Workflow Tests
# ===========================================================================

class TestDualPresignedUrls:
    def test_generate_presigned_urls_returns_both(
        self, storage_service: StorageService, mock_s3_client: MagicMock
    ):
        mock_s3_client.generate_presigned_url.side_effect = [
            "http://host.docker.internal:4566/bucket/uploads/123/sanji?Signature=put_sig",
            "http://host.docker.internal:4566/bucket/uploads/123/sanji?Signature=get_sig",
        ]

        res = run_coro(
            storage_service.generate_presigned_urls(
                filename="sanji",
                content_type="application/octet-stream",
                expires_in=3600,
            )
        )

        assert res.filename == "sanji"
        assert res.content_type == "application/octet-stream"
        assert res.expires_in == 3600
        assert res.upload_url.endswith("put_sig")
        assert res.download_url.endswith("get_sig")
        assert res.key.startswith("uploads/")
        assert res.key.endswith("/sanji")
        assert res.file_id in res.key

        # Verify underlying calls for both PUT and GET
        assert mock_s3_client.generate_presigned_url.call_count == 2
        calls = mock_s3_client.generate_presigned_url.call_args_list
        assert calls[0][0][0] == "put_object"
        assert calls[0][1]["Params"]["ContentType"] == "application/octet-stream"
        assert calls[0][1]["ExpiresIn"] == 3600
        assert calls[1][0][0] == "get_object"
        assert calls[1][1]["Params"]["Key"] == res.key
        assert calls[1][1]["ExpiresIn"] == 3600

    def test_generate_presigned_urls_missing_filename_raises(self, storage_service: StorageService):
        with pytest.raises(StorageValidationError, match="A filename is required for uploads"):
            run_coro(
                storage_service.generate_presigned_urls(
                    filename="",
                )
            )

