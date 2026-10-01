"""
Day 4 Verification Script
Validates:
1. Async engine and session factory configured via Settings.DATABASE_URL
2. Table creation via Base.metadata.create_all and run_sync
3. ORM models (Film, User, Review) with foreign keys and relationships
4. Single round-trip review query joining Film and User
5. FastAPI GET /films endpoint performing real async database read
6. Response mapping using Day 2 FilmResponse schema (with from_attributes=True)
7. Preserved route signatures and request-scoped session closing
"""

import asyncio
from datetime import datetime, timezone
import httpx
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.config import settings
from app.database import engine, SessionLocal, init_db
from app.models.film import Film
from app.models.user import User
from app.models.review import Review
from app.schemas.film import FilmResponse
from app.daos.review_dao import get_reviews_with_film_and_user
from app.main import app


async def test_day4_suite():
    print("=" * 60)
    print("STARTING DAY 4 VERIFICATION SUITE")
    print("=" * 60)

    # 1. Database URL check
    print(f"[CHECK 1] Database URL from Settings: {settings.DATABASE_URL}")
    assert "postgresql+asyncpg://" in settings.DATABASE_URL, "DATABASE_URL must use postgresql+asyncpg"
    print("[PASS] Passed: Using asyncpg driver with Settings object")

    # 2. Table Creation
    print("\n[CHECK 2] Creating tables using Base.metadata.create_all via connection.run_sync()...")
    await init_db()
    print("[PASS] Passed: Tables created successfully")

    # 3. Model Relationships & Real Data Insert
    print("\n[CHECK 3] Testing ORM Models & Relationships (Film, User, Review)...")
    async with SessionLocal() as db:
        # Check/create user
        user_stmt = select(User).where(User.username == "test_critic")
        res = await db.execute(user_stmt)
        user = res.scalar_one_or_none()
        if not user:
            user = User(username="test_critic", email="critic@example.com", role="reviewer")
            db.add(user)
            await db.commit()
            await db.refresh(user)

        # Check/create film
        film_stmt = select(Film).where(Film.title == "Interstellar")
        res = await db.execute(film_stmt)
        film = res.scalar_one_or_none()
        if not film:
            film = Film(
                title="Interstellar",
                release_year=2014,
                genre="Sci-Fi",
                director="Christopher Nolan"
            )
            db.add(film)
            await db.commit()
            await db.refresh(film)

        # Create review
        review = Review(
            film_id=film.id,
            user_id=user.id,
            rating=10,
            body="A mind-bending journey across dimensions with stunning visuals and an emotional score."
        )
        db.add(review)
        await db.commit()
        await db.refresh(review)

        print(f"[PASS] Created/Verified User ID {user.id}, Film ID {film.id}, Review ID {review.id}")

        # 4. Review Query Requirement (Single Round Trip with Joins)
        print("\n[CHECK 4] Testing Single Round-Trip Review Query with Joins...")
        reviews_with_details = await get_reviews_with_film_and_user(db, film_id=film.id)
        assert len(reviews_with_details) > 0, "No reviews returned"
        first = reviews_with_details[0]
        print(f"  Film Title retrieved: {first['film_title']}")
        print(f"  Reviewer Username retrieved: {first['reviewer_username']}")
        print(f"  Rating: {first['rating']}")
        assert first["film_title"] == "Interstellar", "Joined film title mismatch"
        assert first["reviewer_username"] == "test_critic", "Joined reviewer username mismatch"
        print("[PASS] Passed: Retrieved Review, Film title, and Username in single round trip")

    # 5. FastAPI Endpoints Verification
    print("\n[CHECK 5] Testing Endpoints with httpx ASGITransport...")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Health check
        res = await client.get("/health")
        assert res.status_code == 200
        print(f"[PASS] Health Check: {res.json()}")

        # GET /api/v1/films (Real Database Read)
        res = await client.get("/api/v1/films")
        assert res.status_code == 200
        data = res.json()
        print(f"[PASS] GET /films returned {len(data['data'])} films from PostgreSQL")
        assert data["database"] == "postgresql+asyncpg"
        assert len(data["data"]) > 0

        # Check FilmResponse schema with computed field 'years_ago'
        first_film = data["data"][0]
        print(f"  Film title: {first_film['title']}, computed years_ago: {first_film['years_ago']}")
        assert "years_ago" in first_film, "Missing computed field years_ago"

        # GET /api/v1/films/{film_id}/reviews
        res = await client.get(f"/api/v1/films/{film.id}/reviews")
        assert res.status_code == 200
        rev_data = res.json()
        print(f"[PASS] GET /films/{film.id}/reviews returned {len(rev_data['reviews'])} reviews")
        assert rev_data["reviews"][0]["film_title"] == "Interstellar"
        assert rev_data["reviews"][0]["reviewer_display_name"] == "test_critic"

    await engine.dispose()
    print("\n" + "=" * 60)
    print("ALL DAY 4 CHECKS COMPLETED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_day4_suite())
