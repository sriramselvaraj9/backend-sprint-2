"""
tests/integration/test_review_events_integration.py

Integration tests for review event publishing via FastAPI HTTP endpoints.
Tests verify:
- POST /api/v1/films/{film_id}/reviews schedules ReviewCreated event in BackgroundTasks.
- PATCH /api/v1/reviews/{review_id} schedules ReviewUpdated event in BackgroundTasks.
- Normal HTTP responses are returned immediately without waiting for SQS.
"""

import uuid
from unittest.mock import MagicMock

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_event_publisher
from app.main import app as fastapi_app
from app.models.film import Film
from app.models.review import Review
from app.models.user import User
from app.services.event_publisher import EventPublisher

pytestmark = pytest.mark.integration


class TestReviewEventsIntegration:
    """Integration test suite verifying review event publishing through HTTP endpoints."""

    async def test_create_review_endpoint_publishes_event(
        self,
        client: AsyncClient,
        create_film,
        critic_token: str,
        critic_user: User,
    ) -> None:
        """
        Verify that POST /api/v1/films/{film_id}/reviews creates the review in DB
        and publishes a ReviewCreated event with review_id.
        """
        film: Film = await create_film(
            title="Dune: Part Two",
            release_year=2024,
            genre="Sci-Fi",
            director="Denis Villeneuve",
        )

        mock_publisher = MagicMock(spec=EventPublisher)
        fastapi_app.dependency_overrides[get_event_publisher] = lambda: mock_publisher

        try:
            headers = {"Authorization": f"Bearer {critic_token}"}
            payload = {
                "film_id": str(film.id),
                "rating": 10,
                "body": "A visually breathtaking masterpiece with phenomenal sound design.",
            }

            resp = await client.post(
                f"/api/v1/films/{film.id}/reviews",
                json=payload,
                headers=headers,
            )

            assert resp.status_code == 200
            data = resp.json()
            review_id = data["id"]

            # Background task must be executed by AsyncClient
            mock_publisher.publish_review_event.assert_called_once_with(
                event_type="ReviewCreated",
                review_id=review_id,
            )
        finally:
            fastapi_app.dependency_overrides.pop(get_event_publisher, None)

    async def test_update_review_endpoint_publishes_event(
        self,
        client: AsyncClient,
        create_film,
        critic_token: str,
    ) -> None:
        """
        Verify that PATCH /api/v1/reviews/{review_id} updates the review in DB
        and publishes a ReviewUpdated event with review_id.
        """
        film: Film = await create_film(
            title="Blade Runner 2049",
            release_year=2017,
            genre="Sci-Fi",
            director="Denis Villeneuve",
        )

        mock_publisher = MagicMock(spec=EventPublisher)
        fastapi_app.dependency_overrides[get_event_publisher] = lambda: mock_publisher

        try:
            headers = {"Authorization": f"Bearer {critic_token}"}
            post_payload = {
                "film_id": str(film.id),
                "rating": 9,
                "body": "Stunning visuals and philosophical depth.",
            }

            create_resp = await client.post(
                f"/api/v1/films/{film.id}/reviews",
                json=post_payload,
                headers=headers,
            )
            assert create_resp.status_code == 200
            review_id = create_resp.json()["id"]

            mock_publisher.reset_mock()

            patch_payload = {
                "rating": 10,
                "body": "Even better upon second viewing. Absolute masterpiece.",
            }

            patch_resp = await client.patch(
                f"/api/v1/reviews/{review_id}",
                json=patch_payload,
                headers=headers,
            )

            assert patch_resp.status_code == 200
            data = patch_resp.json()
            assert data["status"] == "success"

            mock_publisher.publish_review_event.assert_called_once_with(
                event_type="ReviewUpdated",
                review_id=str(review_id),
            )
        finally:
            fastapi_app.dependency_overrides.pop(get_event_publisher, None)
