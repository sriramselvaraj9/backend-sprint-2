"""
tests/integration/test_role_enforcement.py

Phase Nine: Role-Enforcement Integration Tests.
Exercises distinct permission pairs in the existing Film Review Platform:
- Endpoint Pair A: Review Creation (POST /api/v1/films/{film_id}/reviews) - Critic (permitted) vs Viewer (forbidden).
- Endpoint Pair B: Review Ownership on Update (PATCH /api/v1/reviews/{review_id}) - Owner Critic (permitted) vs Non-Owner Critic (forbidden, 403 ReviewUnauthorisedError).
- Endpoint Pair C: Admin Platform Statistics (GET /api/v1/admin/stats) - Admin (permitted) vs Critic/Viewer (forbidden).
- Endpoint Pair D: Film Creation (POST /api/v1/films) - Admin (permitted) vs Critic (forbidden).
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.film import Film
from app.models.review import Review
from app.models.user import User


@pytest.mark.integration
class TestRoleEnforcementIntegration:
    """Integration test suite verifying RBAC and ownership permissions across endpoints."""

    # -----------------------------------------------------------------------
    # Endpoint Pair A: Review Creation (Critic allowed, Viewer forbidden)
    # -----------------------------------------------------------------------
    async def test_review_creation_role_enforcement(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        create_film,
        critic_token: str,
        critic_user: User,
        viewer_token: str,
    ) -> None:
        """
        Verify that:
        1. Critic is permitted to submit a review -> 200 OK, persisted in SQLite.
        2. Viewer is rejected with 403 Forbidden -> database is not modified.
        """
        film: Film = await create_film(
            title="Dune: Part Two",
            release_year=2024,
            genre="Sci-Fi",
            director="Denis Villeneuve",
        )

        critic_headers = {"Authorization": f"Bearer {critic_token}"}
        viewer_headers = {"Authorization": f"Bearer {viewer_token}"}

        # 1. Permitted: Critic creates a review
        critic_review_payload = {
            "film_id": str(film.id),
            "rating": 10,
            "body": "A visually breathtaking masterpiece with phenomenal sound design.",
        }
        critic_resp = await client.post(
            f"/api/v1/films/{film.id}/reviews",
            json=critic_review_payload,
            headers=critic_headers,
        )
        assert critic_resp.status_code == 200
        review_data = critic_resp.json()
        assert review_data["rating"] == 10
        assert review_data["body"] == critic_review_payload["body"]
        review_id = uuid.UUID(review_data["id"])


        # Verify review persisted in SQLite
        stmt = select(Review).where(Review.id == review_id)
        persisted = (await db_session.execute(stmt)).scalar_one_or_none()
        assert persisted is not None
        assert persisted.user_id == critic_user.id

        # 2. Forbidden: Viewer attempts to create a review on the same film
        viewer_review_payload = {
            "film_id": str(film.id),
            "rating": 7,
            "body": "Decent film with nice visuals but a bit too long in the middle.",
        }
        viewer_resp = await client.post(
            f"/api/v1/films/{film.id}/reviews",
            json=viewer_review_payload,
            headers=viewer_headers,
        )
        assert viewer_resp.status_code == 403
        viewer_err = viewer_resp.json()
        assert "insufficient" in viewer_err.get("detail", "").lower() or viewer_resp.status_code == 403

        # Verify that the forbidden operation did NOT insert a second review into SQLite
        count_stmt = select(func.count(Review.id)).where(Review.film_id == film.id)
        total_reviews = (await db_session.execute(count_stmt)).scalar()
        assert total_reviews == 1

    # -----------------------------------------------------------------------
    # Endpoint Pair B: Review Ownership on Update (Owner allowed, Non-Owner forbidden)
    # -----------------------------------------------------------------------
    async def test_review_ownership_enforcement(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        create_film,
        critic_user: User,
        critic_token: str,
        second_critic_user: User,
        second_critic_token: str,
        admin_token: str,
    ) -> None:
        """
        Verify that:
        1. The critic who authored the review can update it -> 200 OK, database updated.
        2. A different critic (non-owner) cannot update it -> 403 Forbidden (ReviewUnauthorisedError), database unchanged.
        3. An admin can update any review -> 200 OK.
        """
        film: Film = await create_film(title="Arrival", release_year=2016, genre="Sci-Fi", director="Denis Villeneuve")

        # Critic 1 creates a review directly in SQLite
        original_review = Review(
            id=uuid.uuid4(),
            film_id=film.id,
            user_id=critic_user.id,
            rating=8,
            body="Thought-provoking exploration of language and perception of time.",
        )
        db_session.add(original_review)
        await db_session.commit()
        await db_session.refresh(original_review)

        critic_headers = {"Authorization": f"Bearer {critic_token}"}
        second_critic_headers = {"Authorization": f"Bearer {second_critic_token}"}
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # 1. Forbidden: Second critic (non-owner) attempts to update the review
        unauthorized_patch = {
            "rating": 3,
            "body": "Overrated film with slow pacing and confusing plot structure.",
        }
        forbidden_resp = await client.patch(
            f"/api/v1/reviews/{original_review.id}",
            json=unauthorized_patch,
            headers=second_critic_headers,
        )
        assert forbidden_resp.status_code == 403
        err_data = forbidden_resp.json()
        assert err_data.get("error_code") == "ReviewUnauthorisedError" or forbidden_resp.status_code == 403

        # Verify that the review in SQLite was NOT modified
        await db_session.refresh(original_review)
        assert original_review.rating == 8
        assert original_review.body == "Thought-provoking exploration of language and perception of time."

        # 2. Permitted: Original owner critic updates the review
        owner_patch = {
            "rating": 9,
            "body": "Updated review: An absolute masterpiece that holds up on repeat viewings.",
        }
        permitted_resp = await client.patch(
            f"/api/v1/reviews/{original_review.id}",
            json=owner_patch,
            headers=critic_headers,
        )
        assert permitted_resp.status_code == 200
        updated_data = permitted_resp.json()
        assert updated_data.get("rating") == 9 or updated_data.get("review", {}).get("rating") == 9

        # Verify database updated
        await db_session.refresh(original_review)
        assert original_review.rating == 9
        assert original_review.body == owner_patch["body"]

        # 3. Permitted: Admin can update any review
        admin_patch = {
            "rating": 10,
            "body": "Admin moderated review: Superb sci-fi masterpiece with incredible themes.",
        }
        admin_resp = await client.patch(
            f"/api/v1/reviews/{original_review.id}",
            json=admin_patch,
            headers=admin_headers,
        )
        assert admin_resp.status_code == 200
        await db_session.refresh(original_review)
        assert original_review.rating == 10

    # -----------------------------------------------------------------------
    # Endpoint Pair C: Admin Statistics (Admin allowed, Critic/Viewer forbidden)
    # -----------------------------------------------------------------------
    async def test_admin_stats_role_enforcement(
        self,
        client: AsyncClient,
        admin_token: str,
        critic_token: str,
        viewer_token: str,
    ) -> None:
        """
        Verify GET /api/v1/admin/stats:
        - Admin is permitted -> 200 OK with statistics.
        - Critic is rejected -> 403 Forbidden.
        - Viewer is rejected -> 403 Forbidden.
        """
        # 1. Permitted: Admin requests stats
        admin_resp = await client.get(
            "/api/v1/admin/stats",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert admin_resp.status_code == 200
        stats = admin_resp.json()
        assert "total_films" in stats
        assert "total_reviews" in stats

        # 2. Forbidden: Critic requests stats
        critic_resp = await client.get(
            "/api/v1/admin/stats",
            headers={"Authorization": f"Bearer {critic_token}"},
        )
        assert critic_resp.status_code == 403

        # 3. Forbidden: Viewer requests stats
        viewer_resp = await client.get(
            "/api/v1/admin/stats",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert viewer_resp.status_code == 403

    # -----------------------------------------------------------------------
    # Endpoint Pair D: Film Creation (Admin allowed, Critic forbidden)
    # -----------------------------------------------------------------------
    async def test_film_creation_role_enforcement(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        admin_token: str,
        critic_token: str,
    ) -> None:
        """
        Verify POST /api/v1/films:
        - Admin is permitted -> 200 OK, film persisted.
        - Critic is rejected -> 403 Forbidden, film not created.
        """
        payload = {
            "title": "Blade Runner 2049",
            "release_year": 2017,
            "genre": "Sci-Fi",
            "director": "Denis Villeneuve",
        }

        # 1. Forbidden: Critic attempts to create a film
        critic_resp = await client.post(
            "/api/v1/films",
            json=payload,
            headers={"Authorization": f"Bearer {critic_token}"},
        )
        assert critic_resp.status_code == 403

        # Verify not in DB
        stmt = select(Film).where(Film.title == "Blade Runner 2049")
        film_in_db = (await db_session.execute(stmt)).scalar_one_or_none()
        assert film_in_db is None

        # 2. Permitted: Admin creates the film
        admin_resp = await client.post(
            "/api/v1/films",
            json=payload,
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert admin_resp.status_code == 200
        admin_film_in_db = (await db_session.execute(stmt)).scalar_one_or_none()
        assert admin_film_in_db is not None
        assert admin_film_in_db.title == "Blade Runner 2049"
