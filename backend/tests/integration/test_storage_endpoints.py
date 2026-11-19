"""
backend/tests/integration/test_storage_endpoints.py

Integration tests for S3 File Storage HTTP API endpoints:
- POST /api/v1/files (upload PDF, images, validation)
- GET /api/v1/files/{file_id} (stream download, headers, 404 handling)
- GET /api/v1/files (listing, prefix filtering)
- DELETE /api/v1/files/{file_id} (deletion, 404 handling)
- Centralized exception handling to HTTP responses (404, 500)
- Role authentication verification
"""

import uuid
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError
from httpx import AsyncClient

from app.core.config import settings
from app.dependencies import get_storage_service
from app.main import app as fastapi_app
from app.services.storage_service import StorageService
from tests.unit.test_storage_service import FakeS3Client

pytestmark = pytest.mark.integration


@pytest.fixture
def fake_s3_storage() -> FakeS3Client:
    return FakeS3Client(bucket_name="film-review-assets")


@pytest.fixture
def integration_storage_service(fake_s3_storage: FakeS3Client) -> StorageService:
    return StorageService(
        settings=settings,
        s3_client=fake_s3_storage,
        bucket_name="film-review-assets",
    )


@pytest.fixture(autouse=True)
def override_storage_dependency(integration_storage_service: StorageService):
    """Override get_storage_service with our test storage service instance."""
    fastapi_app.dependency_overrides[get_storage_service] = lambda: integration_storage_service
    yield
    fastapi_app.dependency_overrides.pop(get_storage_service, None)


class TestStorageEndpointsIntegration:
    """Integration test suite covering /api/v1/files HTTP endpoints."""

    async def test_upload_pdf_file_success(
        self,
        client: AsyncClient,
        viewer_token: str,
    ):
        """Upload a PDF press kit file via multipart/form-data and verify response."""
        pdf_bytes = b"%PDF-1.4 sample film press kit binary content"
        files = {
            "file": ("press_kit.pdf", pdf_bytes, "application/pdf"),
        }
        headers = {"Authorization": f"Bearer {viewer_token}"}

        response = await client.post("/api/v1/files", files=files, headers=headers)

        assert response.status_code == 201
        data = response.json()
        assert data["filename"] == "press_kit.pdf"
        assert data["content_type"] == "application/pdf"
        assert data["size"] == len(pdf_bytes)
        assert "file_id" in data
        assert uuid.UUID(data["file_id"])  # Valid UUID
        assert data["key"] == f"film-assets/{data['file_id']}/press_kit.pdf"

    async def test_upload_image_file_success(
        self,
        client: AsyncClient,
        viewer_token: str,
    ):
        """Upload an image file (poster.jpg) and verify metadata."""
        img_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 50
        files = {
            "file": ("poster.jpg", img_bytes, "image/jpeg"),
        }
        headers = {"Authorization": f"Bearer {viewer_token}"}

        response = await client.post("/api/v1/files", files=files, headers=headers)

        assert response.status_code == 201
        data = response.json()
        assert data["filename"] == "poster.jpg"
        assert data["content_type"] == "image/jpeg"
        assert data["size"] == len(img_bytes)

    async def test_retrieve_and_stream_file_success(
        self,
        client: AsyncClient,
        viewer_token: str,
    ):
        """Upload a file, then retrieve and stream it via GET /api/v1/files/{file_id}."""
        file_content = b"Streamable film sound clip binary data"
        files = {
            "file": ("audio.wav", file_content, "audio/wav"),
        }
        headers = {"Authorization": f"Bearer {viewer_token}"}

        upload_res = await client.post("/api/v1/files", files=files, headers=headers)
        assert upload_res.status_code == 201
        file_id = upload_res.json()["file_id"]

        # Retrieve file
        get_res = await client.get(f"/api/v1/files/{file_id}", headers=headers)

        assert get_res.status_code == 200
        assert get_res.content == file_content
        assert "audio/wav" in get_res.headers.get("content-type", "")
        assert 'filename="audio.wav"' in get_res.headers.get("content-disposition", "")
        assert get_res.headers.get("content-length") == str(len(file_content))

    async def test_retrieve_nonexistent_file_returns_404(
        self,
        client: AsyncClient,
        viewer_token: str,
    ):
        """Verify requesting a nonexistent file returns 404 with standard error format."""
        missing_id = str(uuid.uuid4())
        headers = {"Authorization": f"Bearer {viewer_token}"}

        response = await client.get(f"/api/v1/files/{missing_id}", headers=headers)

        assert response.status_code == 404
        data = response.json()
        assert data["error_code"] == "STORAGE_OBJECT_NOT_FOUND"
        assert data["status_code"] == 404
        assert "detail" in data

    async def test_list_files_with_prefix(
        self,
        client: AsyncClient,
        viewer_token: str,
    ):
        """Upload multiple files and verify listing and prefix filtering."""
        headers = {"Authorization": f"Bearer {viewer_token}"}

        # Upload two files
        await client.post(
            "/api/v1/files",
            files={"file": ("img1.png", b"data1", "image/png")},
            headers=headers,
        )
        await client.post(
            "/api/v1/files",
            files={"file": ("img2.png", b"data2", "image/png")},
            headers=headers,
        )

        # List all files
        list_res = await client.get("/api/v1/files", headers=headers)
        assert list_res.status_code == 200
        data = list_res.json()
        assert data["total"] >= 2
        assert len(data["files"]) >= 2

        # List with specific prefix
        prefix_res = await client.get("/api/v1/files?prefix=film-assets/", headers=headers)
        assert prefix_res.status_code == 200
        prefix_data = prefix_res.json()
        assert prefix_data["total"] >= 2
        for f in prefix_data["files"]:
            assert f["key"].startswith("film-assets/")

    async def test_delete_existing_file_and_subsequent_404(
        self,
        client: AsyncClient,
        viewer_token: str,
    ):
        """Upload a file, delete it, verify 200 OK, and confirm it can no longer be retrieved."""
        headers = {"Authorization": f"Bearer {viewer_token}"}
        upload_res = await client.post(
            "/api/v1/files",
            files={"file": ("temp.txt", b"temporary", "text/plain")},
            headers=headers,
        )
        file_id = upload_res.json()["file_id"]

        # Delete the file
        delete_res = await client.delete(f"/api/v1/files/{file_id}", headers=headers)
        assert delete_res.status_code == 200
        del_data = delete_res.json()
        assert del_data["deleted"] is True
        assert del_data["file_id"] == file_id

        # Subsequent retrieval should return 404
        get_res = await client.get(f"/api/v1/files/{file_id}", headers=headers)
        assert get_res.status_code == 404

        # Subsequent deletion should also return 404
        delete_again = await client.delete(f"/api/v1/files/{file_id}", headers=headers)
        assert delete_again.status_code == 404

    async def test_unauthenticated_request_rejected(
        self,
        client: AsyncClient,
    ):
        """Verify that requests without an authorization header are rejected with 401."""
        response = await client.get("/api/v1/files")
        assert response.status_code == 401

    async def test_infrastructure_error_handling_http_500(
        self,
        client: AsyncClient,
        viewer_token: str,
    ):
        """Simulate an S3 NoSuchBucket error and verify response maps to HTTP 500."""
        headers = {"Authorization": f"Bearer {viewer_token}"}

        # Mock storage service that triggers NoSuchBucket
        mock_s3 = MagicMock()
        mock_s3.head_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchBucket", "Message": "Bucket does not exist"}},
            "HeadObject",
        )
        error_service = StorageService(
            settings=settings,
            s3_client=mock_s3,
            bucket_name="nonexistent-bucket",
        )
        fastapi_app.dependency_overrides[get_storage_service] = lambda: error_service

        response = await client.get("/api/v1/files/any-id", headers=headers)
        assert response.status_code == 500
        data = response.json()
        assert data["error_code"] == "STORAGE_BUCKET_NOT_FOUND"
        assert data["status_code"] == 500
