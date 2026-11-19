"""
backend/tests/unit/test_storage_endpoints_presigned.py

Unit tests for StorageHandler and API Route endpoints in app/routes/files.py:
1. Handler delegation of generate_presigned_urls, generate_presigned_upload, and generate_presigned_download.
2. POST /files/presigned-urls endpoint returning upload_url and download_url with 201 Created.
3. POST /files/presigned-upload endpoint returning upload_url and download_url with 201 Created.
4. GET /files/{file_id}/presigned-download endpoint.
5. GET /files/exists/{object_key} endpoint.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

import app.core.secrets as _secrets_mod
from app.core.secrets import AppSecrets, DatabaseSecret, JWTSecret

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

from app.handlers.storage_handler import StorageHandler
from app.routes.files import (
    check_file_exists,
    create_presigned_upload,
    generate_presigned_urls,
    get_presigned_download,
)
from app.schemas.storage import (
    PresignedUrlsRequest,
    PresignedUrlsResponse,
    StoragePresignedUrlResponse,
)
from app.schemas.user import AuthenticatedUser
from app.services.storage_service import StorageService

pytestmark = pytest.mark.unit


def run_coro(coro):
    try:
        coro.send(None)
    except StopIteration as exc:
        return exc.value


@pytest.fixture(autouse=True)
def mock_asyncio_to_thread(monkeypatch):
    async def _to_thread(func, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr(asyncio, "to_thread", _to_thread)


@pytest.fixture
def auth_user():
    import uuid
    return AuthenticatedUser(
        id=uuid.uuid4(),
        role="viewer",
        username="testuser",
        email="test@example.com",
    )


class TestStorageHandlerPresigned:
    def test_handler_delegates_presigned_urls(self):
        mock_service = MagicMock(spec=StorageService)
        expected = PresignedUrlsResponse(
            file_id="fc23e716-a92a-402d-8188-a68c7d7c1ea4",
            key="uploads/fc23e716-a92a-402d-8188-a68c7d7c1ea4/sanji",
            filename="sanji",
            content_type="application/octet-stream",
            upload_url="https://s3/put",
            download_url="https://s3/get",
            expires_in=3600,
        )
        mock_service.generate_presigned_urls = AsyncMock(return_value=expected)

        handler = StorageHandler(service=mock_service)
        res = run_coro(
            handler.generate_presigned_urls(
                filename="sanji",
                content_type="application/octet-stream",
                expires_in=3600,
                prefix="uploads",
            )
        )

        assert res == expected
        mock_service.generate_presigned_urls.assert_called_once_with(
            filename="sanji",
            content_type="application/octet-stream",
            expires_in=3600,
            prefix="uploads",
            file_size=None,
        )

    def test_handler_delegates_presigned_upload(self):
        mock_service = MagicMock(spec=StorageService)
        expected = StoragePresignedUrlResponse(
            object_key="uploads/key/file.png",
            url="https://s3/test",
            http_method="PUT",
            expires_in=600,
            headers={"Content-Type": "image/png"},
        )
        mock_service.generate_presigned_upload = AsyncMock(return_value=expected)

        handler = StorageHandler(service=mock_service)
        res = run_coro(
            handler.generate_presigned_upload(
                filename="file.png",
                content_type="image/png",
                file_size=1000,
                prefix="uploads",
                expiry=600,
            )
        )

        assert res == expected
        mock_service.generate_presigned_upload.assert_called_once_with(
            filename="file.png",
            content_type="image/png",
            file_size=1000,
            prefix="uploads",
            expiry=600,
        )

    def test_handler_delegates_presigned_download(self):
        mock_service = MagicMock(spec=StorageService)
        expected = StoragePresignedUrlResponse(
            object_key="uploads/key/file.png",
            url="https://s3/test-get",
            http_method="GET",
            expires_in=300,
            headers={},
        )
        mock_service.generate_presigned_download = AsyncMock(return_value=expected)

        handler = StorageHandler(service=mock_service)
        res = run_coro(
            handler.generate_presigned_download(
                file_id_or_key="file-123",
                expiry=300,
                content_disposition="inline",
            )
        )

        assert res == expected
        mock_service.generate_presigned_download.assert_called_once_with(
            file_id_or_key="file-123",
            expiry=300,
            content_disposition="inline",
        )

    def test_handler_delegates_file_exists(self):
        mock_service = MagicMock(spec=StorageService)
        mock_service.file_exists = AsyncMock(return_value=True)

        handler = StorageHandler(service=mock_service)
        res = run_coro(handler.file_exists("uploads/key/file.png"))

        assert res is True
        mock_service.file_exists.assert_called_once_with(object_key="uploads/key/file.png")


class TestFilesRoutePresignedEndpoints:
    def test_generate_presigned_urls_route(self, auth_user):
        mock_handler = MagicMock(spec=StorageHandler)
        expected = PresignedUrlsResponse(
            file_id="fc23e716-a92a-402d-8188-a68c7d7c1ea4",
            key="uploads/fc23e716-a92a-402d-8188-a68c7d7c1ea4/sanji",
            filename="sanji",
            content_type="application/octet-stream",
            upload_url="http://host.docker.internal:4566/put-url",
            download_url="http://host.docker.internal:4566/get-url",
            expires_in=3600,
        )
        mock_handler.generate_presigned_urls = AsyncMock(return_value=expected)

        payload = PresignedUrlsRequest(
            filename="sanji",
            content_type="application/octet-stream",
            expires_in=3600,
        )

        res = run_coro(generate_presigned_urls(payload=payload, current_user=auth_user, handler=mock_handler))
        assert res == expected
        mock_handler.generate_presigned_urls.assert_called_once_with(
            filename="sanji",
            content_type="application/octet-stream",
            expires_in=3600,
            prefix="uploads",
            file_size=None,
        )

    def test_create_presigned_upload_route(self, auth_user):
        mock_handler = MagicMock(spec=StorageHandler)
        expected = PresignedUrlsResponse(
            file_id="fc23e716-a92a-402d-8188-a68c7d7c1ea4",
            key="uploads/fc23e716-a92a-402d-8188-a68c7d7c1ea4/banner.jpg",
            filename="banner.jpg",
            content_type="image/jpeg",
            upload_url="https://s3/presigned-put",
            download_url="https://s3/presigned-get",
            expires_in=900,
        )
        mock_handler.generate_presigned_urls = AsyncMock(return_value=expected)

        payload = PresignedUrlsRequest(
            filename="banner.jpg",
            content_type="image/jpeg",
            file_size=15000,
            prefix="uploads",
            expiry=900,
        )

        res = run_coro(create_presigned_upload(payload=payload, current_user=auth_user, handler=mock_handler))
        assert res == expected
        mock_handler.generate_presigned_urls.assert_called_once_with(
            filename="banner.jpg",
            content_type="image/jpeg",
            expires_in=900,
            prefix="uploads",
            file_size=15000,
        )

    def test_empty_string_expiry_and_prefix_handles_cleanly(self):
        """Verify that Bruno sending empty strings for prefix/expiry parses cleanly without 422 error."""
        req = PresignedUrlsRequest(
            filename="sanji",
            content_type="application/octet-stream",
            prefix="",
            expiry="",
            file_size="",
        )
        assert req.prefix == "uploads"
        assert req.expiry is None
        assert req.expires_in is None
        assert req.file_size is None

    def test_get_presigned_download_route(self, auth_user):
        mock_handler = MagicMock(spec=StorageHandler)
        expected = StoragePresignedUrlResponse(
            object_key="film-assets/123/banner.jpg",
            url="https://s3/presigned-get",
            http_method="GET",
            expires_in=600,
            headers={},
        )
        mock_handler.generate_presigned_download = AsyncMock(return_value=expected)

        res = run_coro(
            get_presigned_download(
                file_id="123",
                expiry=600,
                content_disposition="attachment",
                current_user=auth_user,
                handler=mock_handler,
            )
        )
        assert res == expected
        mock_handler.generate_presigned_download.assert_called_once_with(
            file_id_or_key="123",
            expiry=600,
            content_disposition="attachment",
        )

    def test_check_file_exists_route(self, auth_user):
        mock_handler = MagicMock(spec=StorageHandler)
        mock_handler.file_exists = AsyncMock(return_value=True)

        res = run_coro(check_file_exists(object_key="uploads/test.jpg", current_user=auth_user, handler=mock_handler))
        assert res == {"exists": True}
        mock_handler.file_exists.assert_called_once_with("uploads/test.jpg")
