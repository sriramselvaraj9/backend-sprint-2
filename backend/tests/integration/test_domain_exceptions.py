"""
tests/integration/test_domain_exceptions.py

Integration tests for the centralized domain-exception handler.
Verifies that domain exceptions raised in application layers (Service, DAO, Route)
are intercepted by the centralized exception handler and translated into structured
HTTP responses with correct HTTP status codes, 'type' field, 'message' string,
'error_code', and structured 'detail'.
"""

import uuid

import pytest
from httpx import AsyncClient

from app.exceptions.domain import (
    DomainError,
)
from app.main import app as fastapi_app

pytestmark = pytest.mark.integration


class TestCentralizedExceptionHandler:
    """Test suite for centralized domain exception handler through real HTTP requests."""

    async def test_film_not_found_exception_response_shape(
        self,
        client: AsyncClient,
        viewer_token: str,
    ) -> None:
        """
        Trigger FilmNotFoundError by querying a nonexistent UUID via GET /api/v1/films/{film_id}.
        Assert:
        - HTTP status code 404
        - JSON response contains 'type' equal to 'FilmNotFoundError'
        - 'message' is a non-empty string
        - 'error_code' is 'FILM_NOT_FOUND'
        - 'detail' contains the requested film ID
        """
        nonexistent_film_id = uuid.uuid4()
        headers = {"Authorization": f"Bearer {viewer_token}"}

        response = await client.get(f"/api/v1/films/{nonexistent_film_id}", headers=headers)

        assert response.status_code == 404
        payload = response.json()

        # Assert mandatory requirement fields
        assert payload["type"] == "FilmNotFoundError"
        assert isinstance(payload["message"], str)
        assert len(payload["message"].strip()) > 0
        assert str(nonexistent_film_id) in payload["message"]

        # Assert structured response contract
        assert payload["status_code"] == 404
        assert payload["error_code"] == "FILM_NOT_FOUND"
        assert payload["detail"] is not None
        assert payload["detail"]["film_id"] == str(nonexistent_film_id)

    async def test_user_already_exists_exception_response_shape(
        self,
        client: AsyncClient,
    ) -> None:
        """
        Trigger UserAlreadyExistsError by submitting duplicate registration credentials.
        Assert:
        - HTTP status code 400
        - JSON response contains 'type' equal to 'UserAlreadyExistsError'
        - 'message' is a non-empty string
        - 'error_code' is 'USER_ALREADY_EXISTS'
        """
        user_payload = {
            "username": "duplicate_handler_test",
            "email": "duplicate_handler@example.com",
            "password": "SecurePassword123!",
        }

        # First registration succeeds
        resp1 = await client.post("/api/v1/auth/register", json=user_payload)
        assert resp1.status_code == 201

        # Second registration fails with UserAlreadyExistsError
        resp2 = await client.post("/api/v1/auth/register", json=user_payload)
        assert resp2.status_code == 400
        payload = resp2.json()

        assert payload["type"] == "UserAlreadyExistsError"
        assert isinstance(payload["message"], str)
        assert len(payload["message"].strip()) > 0
        assert payload["status_code"] == 400
        assert payload["error_code"] == "USER_ALREADY_EXISTS"

    async def test_film_has_active_reviews_conflict_exception(
        self,
        client: AsyncClient,
        admin_token: str,
        critic_token: str,
        create_film,
    ) -> None:
        """
        Trigger FilmHasActiveReviewsError by attempting to delete a film that has active reviews.
        Assert:
        - HTTP status code 409 Conflict
        - 'type' is 'FilmHasActiveReviewsError'
        - 'message' is a non-empty string
        - 'error_code' is 'FILM_HAS_ACTIVE_REVIEWS'
        - 'detail' contains active_review_count
        """
        # 1. Create active film
        film = await create_film(title="Reviewed Masterpiece", release_year=2020)

        # 2. Add an active review
        critic_headers = {"Authorization": f"Bearer {critic_token}"}
        review_payload = {
            "film_id": str(film.id),
            "rating": 10,
            "body": "Phenomenal direction and cinematography.",
        }
        review_resp = await client.post(
            f"/api/v1/films/{film.id}/reviews",
            headers=critic_headers,
            json=review_payload,
        )
        assert review_resp.status_code == 200

        # 3. Admin attempts to delete the film (business rule forbids deletion with active reviews)
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        delete_resp = await client.delete(f"/api/v1/films/{film.id}", headers=admin_headers)

        assert delete_resp.status_code == 409
        payload = delete_resp.json()

        assert payload["type"] == "FilmHasActiveReviewsError"
        assert isinstance(payload["message"], str)
        assert len(payload["message"].strip()) > 0
        assert payload["status_code"] == 409
        assert payload["error_code"] == "FILM_HAS_ACTIVE_REVIEWS"
        assert payload["detail"]["active_review_count"] == 1

    async def test_review_already_exists_conflict_exception(
        self,
        client: AsyncClient,
        critic_token: str,
        create_film,
    ) -> None:
        """
        Trigger ReviewAlreadyExistsError by submitting duplicate reviews from the same critic for one film.
        Assert:
        - HTTP status code 409 Conflict
        - 'type' is 'ReviewAlreadyExistsError'
        - 'message' is a non-empty string
        - 'error_code' is 'REVIEW_ALREADY_EXISTS'
        """
        film = await create_film(title="Single Review Film", release_year=2022)
        critic_headers = {"Authorization": f"Bearer {critic_token}"}
        review_payload = {
            "film_id": str(film.id),
            "rating": 8,
            "body": "Great first impressions.",
        }

        # First review succeeds
        r1 = await client.post(f"/api/v1/films/{film.id}/reviews", headers=critic_headers, json=review_payload)
        assert r1.status_code == 200

        # Second review from same user for same film raises ReviewAlreadyExistsError
        r2 = await client.post(f"/api/v1/films/{film.id}/reviews", headers=critic_headers, json=review_payload)
        assert r2.status_code == 409
        payload = r2.json()

        assert payload["type"] == "ReviewAlreadyExistsError"
        assert isinstance(payload["message"], str)
        assert len(payload["message"].strip()) > 0
        assert payload["status_code"] == 409
        assert payload["error_code"] == "REVIEW_ALREADY_EXISTS"

    async def test_invalid_cursor_domain_exception(
        self,
        client: AsyncClient,
        viewer_token: str,
    ) -> None:
        """
        Trigger InvalidCursorError via GET /api/v1/films/cursor with a malformed cursor string.
        Assert:
        - HTTP status code 400 Bad Request
        - 'type' is 'InvalidCursorError'
        - 'message' is a non-empty string
        - 'error_code' is 'INVALID_CURSOR'
        """
        headers = {"Authorization": f"Bearer {viewer_token}"}
        response = await client.get("/api/v1/films/cursor?cursor=not-a-valid-base64-uuid", headers=headers)

        assert response.status_code == 400
        payload = response.json()

        assert payload["type"] == "InvalidCursorError"
        assert isinstance(payload["message"], str)
        assert len(payload["message"].strip()) > 0
        assert payload["status_code"] == 400
        assert payload["error_code"] == "INVALID_CURSOR"

    async def test_base_domain_error_handler_fallback(
        self,
        client: AsyncClient,
    ) -> None:
        """
        Trigger the fallback base DomainError handler via a controlled test endpoint.
        Assert that non-specialized DomainErrors are handled with their declared status_code,
        message, error_code, and type.
        """
        endpoint_path = "/api/v1/test-domain-error"

        # Check existing routes using getattr to handle any router types
        has_route = any(getattr(route, "path", None) == endpoint_path for route in fastapi_app.routes)
        if not has_route:
            @fastapi_app.get(endpoint_path, include_in_schema=False)
            async def _raise_domain_error():
                raise DomainError(
                    message="Fallback base domain failure occurred",
                    error_code="TEST_FALLBACK_ERROR",
                    status_code=422,
                    detail={"sample_field": "sample_value"},
                )

        response = await client.get(endpoint_path)
        assert response.status_code == 422
        payload = response.json()

        assert payload["type"] == "DomainError"
        assert payload["message"] == "Fallback base domain failure occurred"
        assert payload["status_code"] == 422
        assert payload["error_code"] == "TEST_FALLBACK_ERROR"
        assert payload["detail"] == {"sample_field": "sample_value"}
