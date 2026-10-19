"""
tests/integration/test_background_aggregation.py

Integration tests for the background aggregation task (recalculate_film_review_aggregates).
Tests direct execution of the background task function against the isolated SQLite test database
and verified in-memory fake Redis without production infrastructure dependencies.
"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import app.core.database
import app.core.redis
from app.models.film import Film
from app.models.review import Review
from app.services.film_service import recalculate_film_review_aggregates

pytestmark = pytest.mark.integration


class TestBackgroundAggregationTask:
    """Test suite directly executing and verifying the background review aggregation task."""

    async def test_recalculate_aggregates_multiple_reviews_updates_film(
        self,
        db_session: AsyncSession,
        test_session_factory: async_sessionmaker[AsyncSession],
        fake_redis,
        monkeypatch: pytest.MonkeyPatch,
        create_user,
    ) -> None:
        """
        Background Aggregation Task Test:
        - Use the existing test database and fixtures.
        - Create a film and multiple reviews with known ratings.
        - Call the aggregation task function directly, awaiting it.
        - Query the test database after the task completes.
        - Verify review_count equals the number of applicable reviews.
        - Verify average_rating equals the expected average calculated from those reviews.
        - Ensure the test is isolated and does not depend on production DB or real Redis.
        """
        # 1. Ensure background task session factory and Redis point to isolated test infrastructure
        monkeypatch.setattr(app.core.database, "SessionLocal", test_session_factory)
        monkeypatch.setattr(app.core.redis, "redis_client", fake_redis)

        # 2. Create users who will author the reviews
        user1 = await create_user(username="reviewer_1", email="rev1@example.com")
        user2 = await create_user(username="reviewer_2", email="rev2@example.com")
        user3 = await create_user(username="reviewer_3", email="rev3@example.com")

        # 3. Create a film with initial 0 reviews and None average_rating
        film = Film(
            id=uuid.uuid4(),
            title="Dune: Part Two",
            release_year=2024,
            genre="Sci-Fi",
            director="Denis Villeneuve",
            is_active=True,
            review_count=0,
            average_rating=None,
        )
        db_session.add(film)
        await db_session.commit()
        await db_session.refresh(film)

        assert film.review_count == 0
        assert film.average_rating is None

        # 4. Insert multiple reviews with known ratings: 8, 9, 10
        # Expected average = (8 + 9 + 10) / 3 = 9.0
        review1 = Review(film_id=film.id, user_id=user1.id, rating=8, body="Impressive scale and visual spectacle.")
        review2 = Review(film_id=film.id, user_id=user2.id, rating=9, body="Superb pacing and acting.")
        review3 = Review(film_id=film.id, user_id=user3.id, rating=10, body="Masterpiece of modern science fiction.")
        db_session.add_all([review1, review2, review3])
        await db_session.commit()

        # 5. Call the background aggregation task function directly, awaiting it
        await recalculate_film_review_aggregates(film_id=film.id, request_id="test-trace-id-123")

        # 6. Query the test database after the task completes
        async with test_session_factory() as verify_session:
            updated_film = await verify_session.get(Film, film.id)
            assert updated_film is not None

            # 7. Verify review_count equals 3 and average_rating equals 9.0
            assert updated_film.review_count == 3
            assert updated_film.average_rating == 9.0

    async def test_recalculate_aggregates_film_with_zero_reviews(
        self,
        db_session: AsyncSession,
        test_session_factory: async_sessionmaker[AsyncSession],
        fake_redis,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """
        Verify aggregate calculation on a film with zero reviews resets review_count to 0
        and average_rating to None.
        """
        monkeypatch.setattr(app.core.database, "SessionLocal", test_session_factory)
        monkeypatch.setattr(app.core.redis, "redis_client", fake_redis)

        film = Film(
            id=uuid.uuid4(),
            title="Unreviewed Indie Movie",
            release_year=2024,
            genre="Drama",
            director="Indie Filmmaker",
            is_active=True,
            review_count=5,  # Stale count to be corrected
            average_rating=8.0,
        )
        db_session.add(film)
        await db_session.commit()

        # Call aggregation function directly
        await recalculate_film_review_aggregates(film_id=film.id)

        async with test_session_factory() as verify_session:
            refreshed_film = await verify_session.get(Film, film.id)
            assert refreshed_film is not None
            assert refreshed_film.review_count == 0
            assert refreshed_film.average_rating is None

    async def test_recalculate_aggregates_ignores_reviews_for_other_films(
        self,
        db_session: AsyncSession,
        test_session_factory: async_sessionmaker[AsyncSession],
        fake_redis,
        monkeypatch: pytest.MonkeyPatch,
        create_user,
    ) -> None:
        """
        Verify that review aggregation for Film A only counts reviews belonging to Film A,
        ignoring reviews authored for Film B.
        """
        monkeypatch.setattr(app.core.database, "SessionLocal", test_session_factory)
        monkeypatch.setattr(app.core.redis, "redis_client", fake_redis)

        user = await create_user(username="multi_reviewer", email="multi@example.com")

        film_a = Film(id=uuid.uuid4(), title="Target Film A", release_year=2021, genre="Drama", director="Director A")
        film_b = Film(id=uuid.uuid4(), title="Other Film B", release_year=2022, genre="Action", director="Director B")
        db_session.add_all([film_a, film_b])
        await db_session.commit()

        # Film A has rating 6; Film B has rating 10
        r_a = Review(film_id=film_a.id, user_id=user.id, rating=6, body="Decent.")
        r_b = Review(film_id=film_b.id, user_id=user.id, rating=10, body="Incredible.")
        db_session.add_all([r_a, r_b])
        await db_session.commit()

        await recalculate_film_review_aggregates(film_id=film_a.id)

        async with test_session_factory() as verify_session:
            film_a_updated = await verify_session.get(Film, film_a.id)
            assert film_a_updated is not None
            assert film_a_updated.review_count == 1
            assert film_a_updated.average_rating == 6.0

    async def test_recalculate_aggregates_catches_errors_gracefully(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """
        Verify that unexpected exceptions (such as DB failures) during background task
        execution are caught, logged, and do not raise unhandled exceptions.
        """
        class FailingSessionContext:
            async def __aenter__(self):
                raise RuntimeError("Simulated database failure during background recalculation")

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return False

        monkeypatch.setattr(app.core.database, "SessionLocal", lambda: FailingSessionContext())

        # Must complete without unhandled exception bubbling
        await recalculate_film_review_aggregates(
            film_id=uuid.uuid4(),
            request_id="test-failing-trace",
        )

