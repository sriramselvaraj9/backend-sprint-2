import uuid

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.film import Film
from app.models.review import Review
from app.models.user import User


class UserDAO:
    """
    Typed async Data Access Object for the User entity.
    Encapsulates all direct database interaction for users.
    Receives an AsyncSession through dependency injection.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_email(self, email: str) -> User | None:
        """
        Accept email: str.
        Return User | None using select() and scalar_one_or_none().
        Returns None if user does not exist.
        """
        stmt = select(User).where(User.email == email)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        """
        Accept username: str.
        Return User | None using select() and scalar_one_or_none().
        Returns None if user does not exist.
        """
        stmt = select(User).where(User.username == username)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        """
        Accept user_id: uuid.UUID.
        Return User | None using select() and scalar_one_or_none().
        """
        stmt = select(User).where(User.id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, user: User) -> User:
        """
        Accept a User ORM object.
        Add to session, commit, refresh, and return it.
        """
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def get_default_user(self) -> User | None:
        """
        Retrieve a default user (e.g. first registered/seeded user) from the database.
        Used by review service when user_id is omitted.
        """
        stmt = select(User).order_by(User.created_at.asc()).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_admin_stats(self) -> dict:
        """
        Fetch real aggregation statistics from the PostgreSQL database.
        Queries live counts for users, films, reviews, and active database sessions.
        """
        total_users = (await self.session.scalar(select(func.count(User.id)))) or 0
        total_films = (await self.session.scalar(select(func.count(Film.id)).where(Film.is_active == True))) or 0

        total_reviews = (await self.session.scalar(select(func.count(Review.id)))) or 0

        try:
            active_res = await self.session.execute(
                text("SELECT count(*) FROM pg_stat_activity WHERE state = 'active'")
            )
            active_sessions = active_res.scalar() or 1
        except Exception:  # noqa: BLE001
            active_sessions = 1

        return {
            "message": "Admin statistics fetched successfully",
            "stats": {
                "total_users": total_users,
                "total_films": total_films,
                "total_reviews": total_reviews,
                "active_sessions": active_sessions,
            },
        }
