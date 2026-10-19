"""
scripts/seed_sqlite.py

Helper script to initialize and seed a local SQLite database (test.db)
so that it can be inspected in visual database tools like TableForge, DBeaver, or SQLite Viewer.
"""

import asyncio
import os
import sys

# Ensure repository root is on PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.models.film import Film
from app.models.review import Review
from app.models.user import User
from app.models.watchlist import Watchlist
from seed import SEED_FILMS, SEED_REVIEWS, SEED_USERS, SEED_WATCHLIST


async def main() -> None:
    db_path = "test.db"
    print(f"Initializing SQLite database in '{db_path}'...")
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")

    # Drop all and recreate to ensure a clean slate
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as db:
        print("Seeding users...")
        users_by_username: dict[str, User] = {}
        for u in SEED_USERS:
            user = User(**u)
            db.add(user)
            await db.flush()
            users_by_username[user.username] = user

        print("Seeding films...")
        films_by_title: dict[str, Film] = {}
        for f in SEED_FILMS:
            film = Film(**f)
            db.add(film)
            await db.flush()
            films_by_title[film.title] = film

        print("Seeding reviews...")
        for r in SEED_REVIEWS:
            r_username = str(r.get("username", ""))
            r_film_title = str(r.get("film_title", ""))
            target_user = users_by_username.get(r_username)
            target_film = films_by_title.get(r_film_title)
            if target_user is not None and target_film is not None:
                review = Review(
                    user_id=target_user.id,
                    film_id=target_film.id,
                    rating=int(str(r.get("rating", 0))),
                    body=str(r.get("body", "")),
                )
                db.add(review)

        print("Seeding watchlist...")
        for w in SEED_WATCHLIST:
            w_username = str(w.get("username", ""))
            w_film_title = str(w.get("film_title", ""))
            wl_user = users_by_username.get(w_username)
            wl_film = films_by_title.get(w_film_title)
            if wl_user is not None and wl_film is not None:
                watchlist_entry = Watchlist(user_id=wl_user.id, film_id=wl_film.id)
                db.add(watchlist_entry)

        await db.commit()

    await engine.dispose()
    print("Database 'test.db' initialized and seeded successfully!")


if __name__ == "__main__":
    asyncio.run(main())
