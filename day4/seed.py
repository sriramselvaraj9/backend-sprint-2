import asyncio

from sqlalchemy import select

from app.database import SessionLocal, engine
from app.models.film import Film
from app.models.review import Review
from app.models.user import User
from app.models.watchlist import Watchlist

# -----------------------------------------------------------------------------
# Baseline Data Definitions
# -----------------------------------------------------------------------------
SEED_USERS = [
    {
        "username": "alice_admin",
        "email": "alice@example.com",
        "role": "admin",
    },
    {
        "username": "bob_critic",
        "email": "bob@example.com",
        "role": "reviewer",
    },
    {
        "username": "charlie_fan",
        "email": "charlie@example.com",
        "role": "user",
    },
]

SEED_FILMS = [
    {
        "title": "Inception",
        "release_year": 2010,
        "genre": "Sci-Fi",
        "director": "Christopher Nolan",
    },
    {
        "title": "Interstellar",
        "release_year": 2014,
        "genre": "Sci-Fi",
        "director": "Christopher Nolan",
    },
    {
        "title": "The Matrix",
        "release_year": 1999,
        "genre": "Sci-Fi",
        "director": "Lana Wachowski, Lilly Wachowski",
    },
    {
        "title": "The Godfather",
        "release_year": 1972,
        "genre": "Crime",
        "director": "Francis Ford Coppola",
    },
    {
        "title": "Pulp Fiction",
        "release_year": 1994,
        "genre": "Crime",
        "director": "Quentin Tarantino",
    },
    {
        "title": "The Dark Knight",
        "release_year": 2008,
        "genre": "Action",
        "director": "Christopher Nolan",
    },
    {
        "title": "Mad Max: Fury Road",
        "release_year": 2015,
        "genre": "Action",
        "director": "George Miller",
    },
    {
        "title": "Spirited Away",
        "release_year": 2001,
        "genre": "Animation",
        "director": "Hayao Miyazaki",
    },
    {
        "title": "Parasite",
        "release_year": 2019,
        "genre": "Drama",
        "director": "Bong Joon-ho",
    },
    {
        "title": "Whiplash",
        "release_year": 2014,
        "genre": "Drama",
        "director": "Damien Chazelle",
    },
    {
        "title": "The Shawshank Redemption",
        "release_year": 1994,
        "genre": "Drama",
        "director": "Frank Darabont",
    },
    {
        "title": "Blade Runner 2049",
        "release_year": 2017,
        "genre": "Sci-Fi",
        "director": "Denis Villeneuve",
    },
]

SEED_REVIEWS = [
    {
        "film_title": "Inception",
        "username": "alice_admin",
        "rating": 10,
        "body": "A breathtaking masterpiece of layered subconsciousness and practical effects.",
    },
    {
        "film_title": "The Matrix",
        "username": "bob_critic",
        "rating": 9,
        "body": "A groundbreaking sci-fi masterpiece with iconic philosophy and visual style.",
    },
    {
        "film_title": "The Dark Knight",
        "username": "charlie_fan",
        "rating": 10,
        "body": "The definitive superhero crime thriller featuring an iconic performance by Heath Ledger.",
    },
    {
        "film_title": "Parasite",
        "username": "bob_critic",
        "rating": 9,
        "body": "Brilliant social satire that seamlessly shifts between dark comedy and tense thriller.",
    },
    {
        "film_title": "Spirited Away",
        "username": "charlie_fan",
        "rating": 10,
        "body": "An enchanting animated journey brimming with boundless imagination and heart.",
    },
    {
        "film_title": "Pulp Fiction",
        "username": "alice_admin",
        "rating": 8,
        "body": "Sharp dialogue and memorable characters that revolutionized non-linear storytelling.",
    },
]

SEED_WATCHLIST = [
    {
        "username": "charlie_fan",
        "film_title": "Inception",
    },
    {
        "username": "bob_critic",
        "film_title": "Blade Runner 2049",
    },
    {
        "username": "alice_admin",
        "film_title": "Whiplash",
    },
]


# -----------------------------------------------------------------------------
# Seeding Logic (Repeatable / Idempotent)
# -----------------------------------------------------------------------------

async def seed_database() -> None:
    """
    Populates baseline data for users, films, reviews, and watchlist entries.
    Safe to run repeatedly: checks for existing records before inserting.
    """
    print("\n--- Starting Database Seeding ---")

    async with SessionLocal() as db:
        # 1. Seed Users (check by username to prevent duplicates)
        users_by_username: dict[str, User] = {}
        users_created = 0
        for user_data in SEED_USERS:
            stmt = select(User).where(User.username == user_data["username"])
            result = await db.execute(stmt)
            existing_user = result.scalar_one_or_none()

            if existing_user is None:
                new_user = User(**user_data)
                db.add(new_user)
                await db.flush()  # Flush to populate new_user.id
                users_by_username[new_user.username] = new_user
                users_created += 1
                print(f"  [+] Created user: {new_user.username} (role: {new_user.role})")
            else:
                users_by_username[existing_user.username] = existing_user
                print(f"  [=] User already exists: {existing_user.username}")

        # 2. Seed Films (check by title to prevent duplicates)
        films_by_title: dict[str, Film] = {}
        films_created = 0
        for film_data in SEED_FILMS:
            stmt = select(Film).where(Film.title == film_data["title"])
            result = await db.execute(stmt)
            existing_film = result.scalar_one_or_none()

            if existing_film is None:
                new_film = Film(**film_data)
                db.add(new_film)
                await db.flush()  # Flush to populate new_film.id
                films_by_title[new_film.title] = new_film
                films_created += 1
                print(f"  [+] Created film: {new_film.title} ({new_film.release_year}, {new_film.genre})")
            else:
                films_by_title[existing_film.title] = existing_film
                print(f"  [=] Film already exists: {existing_film.title}")

        # 3. Seed Reviews (check by user_id and film_id to prevent duplicates)
        reviews_created = 0
        for rev_data in SEED_REVIEWS:
            # pyrefly: ignore [bad-argument-type]
            user = users_by_username.get(rev_data["username"])
            # pyrefly: ignore [bad-argument-type]
            film = films_by_title.get(rev_data["film_title"])

            if not user or not film:
                continue

            stmt = select(Review).where(
                Review.user_id == user.id,
                Review.film_id == film.id,
            )
            result = await db.execute(stmt)
            existing_review = result.scalar_one_or_none()

            if existing_review is None:
                new_review = Review(
                    user_id=user.id,
                    film_id=film.id,
                    rating=rev_data["rating"],
                    body=rev_data["body"],
                )
                db.add(new_review)
                reviews_created += 1
                print(f"  [+] Created review: '{film.title}' by {user.username} (rating: {new_review.rating})")
            else:
                print(f"  [=] Review already exists: '{film.title}' by {user.username}")

        # 4. Seed Watchlist entries (check by user_id and film_id to prevent duplicates)
        watchlist_created = 0
        for item in SEED_WATCHLIST:
            user = users_by_username.get(item["username"])
            film = films_by_title.get(item["film_title"])

            if not user or not film:
                continue

            stmt = select(Watchlist).where(
                Watchlist.user_id == user.id,
                Watchlist.film_id == film.id,
            )
            result = await db.execute(stmt)
            existing_entry = result.scalar_one_or_none()

            if existing_entry is None:
                new_entry = Watchlist(
                    user_id=user.id,
                    film_id=film.id,
                )
                db.add(new_entry)
                watchlist_created += 1
                print(f"  [+] Added to watchlist: '{film.title}' for {user.username}")
            else:
                print(f"  [=] Watchlist entry already exists: '{film.title}' for {user.username}")

        # Commit all changes to the database
        await db.commit()

    print("\n--- Seeding Summary ---")
    print(f"  Users:     {users_created} created, {len(SEED_USERS) - users_created} already existed")
    print(f"  Films:     {films_created} created, {len(SEED_FILMS) - films_created} already existed")
    print(f"  Reviews:   {reviews_created} created, {len(SEED_REVIEWS) - reviews_created} already existed")
    print(f"  Watchlist: {watchlist_created} created, {len(SEED_WATCHLIST) - watchlist_created} already existed")
    print("--- Database Seeding Completed Successfully ---\n")


async def main() -> None:
    try:
        await seed_database()
    finally:
        # Dispose the connection pool
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
