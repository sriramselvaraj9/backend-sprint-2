"""
tests/integration/test_db_isolation.py

Phase Ten: Database Isolation and Regression Checks.
Demonstrates:
- Clean database state between independent tests (no data leakage).
- Application-level commits do not defeat the isolation/cleanup strategy.
- Foreign-key constraints are actively enforced in SQLite (PRAGMA foreign_keys=ON).
- The test database engine is strictly SQLite (sqlite+aiosqlite) with zero PostgreSQL dependency.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.models.film import Film
from app.models.review import Review
from app.models.user import User


@pytest.mark.integration
class TestDatabaseIsolationAndRegression:
    """Regression checks verifying database isolation, FK constraints, and engine independence."""

    async def test_isolation_phase_a_create_data(
        self,
        db_session: AsyncSession,
    ) -> None:
        """
        Create a film and user in the test database and explicitly commit them.
        Subsequent test must observe a completely empty database.
        """
        film = Film(
            id=uuid.uuid4(),
            title="Isolation Sentinel Film",
            release_year=2020,
            genre="Sci-Fi",
            director="Test Director",
            is_active=True,
        )
        user = User(
            id=uuid.uuid4(),
            username="isolation_user",
            email="isolation@example.com",
            password_hash="mock_hash",
            role="viewer",
        )
        db_session.add_all([film, user])
        await db_session.commit()

        # Confirm data is stored in DB
        film_count = (await db_session.execute(select(func.count(Film.id)))).scalar()
        user_count = (await db_session.execute(select(func.count(User.id)))).scalar()
        assert film_count == 1
        assert user_count == 1

    async def test_isolation_phase_b_verify_clean_state(
        self,
        db_session: AsyncSession,
    ) -> None:
        """
        Independent test confirming that data from test_isolation_phase_a_create_data
        did NOT leak and the database begins in a predictable, completely clean state.
        """
        film_count = (await db_session.execute(select(func.count(Film.id)))).scalar()
        user_count = (await db_session.execute(select(func.count(User.id)))).scalar()
        review_count = (await db_session.execute(select(func.count(Review.id)))).scalar()

        assert film_count == 0, f"Expected 0 films, found {film_count} (data leaked from previous test)"
        assert user_count == 0, f"Expected 0 users, found {user_count} (data leaked from previous test)"
        assert review_count == 0, f"Expected 0 reviews, found {review_count}"

    async def test_app_commits_do_not_defeat_isolation_request_one(
        self,
        client: AsyncClient,
        admin_token: str,
    ) -> None:
        """
        Create a film through real HTTP request which triggers real application commit().
        """
        payload = {
            "title": "Application Commit Film",
            "release_year": 2021,
            "genre": "Drama",
            "director": "Director One",
        }
        resp = await client.post(
            "/api/v1/films",
            json=payload,
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200

    async def test_app_commits_do_not_defeat_isolation_request_two(
        self,
        client: AsyncClient,
        viewer_token: str,
    ) -> None:
        """
        Subsequent independent HTTP test verifying that previous test's application commit
        did not leave records behind in the database catalog.
        """
        resp = await client.get(
            "/api/v1/films",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert resp.status_code == 200
        items = resp.json().get("items", [])
        assert len(items) == 0, f"Expected clean catalog, but found {len(items)} items"

    async def test_foreign_key_constraints_enforced(
        self,
        db_session: AsyncSession,
    ) -> None:
        """
        Verify that foreign key constraints are strictly enforced in the SQLite test database.
        Inserting a review with non-existent film_id or user_id must raise IntegrityError.
        """
        orphan_review = Review(
            id=uuid.uuid4(),
            film_id=uuid.uuid4(),  # Non-existent film
            user_id=uuid.uuid4(),  # Non-existent user
            rating=8,
            body="Review referencing non-existent parent records.",
        )
        db_session.add(orphan_review)
        with pytest.raises(IntegrityError):
            await db_session.commit()

        await db_session.rollback()

    async def test_test_engine_is_isolated_sqlite_not_production_db(
        self,
        test_engine: AsyncEngine,
    ) -> None:
        """
        Verify that the test engine is using sqlite+aiosqlite in-memory,
        and never points to PostgreSQL or production connection strings.
        """
        assert test_engine.url.drivername == "sqlite+aiosqlite"
        assert test_engine.url.database == ":memory:"
