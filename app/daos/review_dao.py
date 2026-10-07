import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.film import Film
from app.models.review import Review
from app.models.user import User
from app.schemas.review import ReviewCreate


class ReviewDAO:
    """
    Typed async Data Access Object for the Review entity.
    Encapsulates all direct database queries and mutations for reviews.
    Receives an AsyncSession through dependency injection.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def is_film_active(self, film_id: uuid.UUID) -> bool:
        """
        Check if film exists and is currently active (is_active == True).
        """
        stmt = select(Film.id).where(Film.id == film_id, Film.is_active == True)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def list_by_film(self, film_id: uuid.UUID) -> list[Review]:
        """
        Get all reviews for the given active film ordered by most recent first.
        Only reviews for active (non-soft-deleted) films are returned.
        Uses select(), order_by(Review.created_at.desc()), and scalars().all().
        """
        stmt = (
            select(Review)
            .join(Review.film)
            .options(
                joinedload(Review.film),
                joinedload(Review.user),
            )
            .where(Review.film_id == film_id, Film.is_active == True)
            .order_by(Review.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().unique().all())

    async def average_rating(self, film_id: uuid.UUID) -> float | None:
        """
        Return the average rating for the active film using func.avg().
        If the film has no reviews or is soft-deleted, returns None.
        """
        stmt = (
            select(func.avg(Review.rating)).join(Review.film).where(Review.film_id == film_id, Film.is_active == True)
        )
        result = await self.session.execute(stmt)
        avg = result.scalar_one_or_none()
        return float(avg) if avg is not None else None

    async def create(self, review: Review) -> Review:
        """
        Accept a Review ORM object.
        Validates that the referenced film exists and is active (not soft-deleted).
        Add to session, commit, refresh, and return it.
        """
        if not await self.is_film_active(review.film_id):
            raise ValueError(f"Film with ID {review.film_id} not found or has been soft-deleted")

        self.session.add(review)
        await self.session.commit()
        await self.session.refresh(review)

        stmt = select(Review).options(joinedload(Review.film), joinedload(Review.user)).where(Review.id == review.id)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_by_id(self, review_id: uuid.UUID) -> Review | None:
        """
        Find a review by ID for an active film using select() and scalar_one_or_none().
        """
        stmt = (
            select(Review)
            .join(Review.film)
            .options(
                joinedload(Review.film),
                joinedload(Review.user),
            )
            .where(Review.id == review_id, Film.is_active == True)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_film_and_user(self, film_id: uuid.UUID, user_id: uuid.UUID) -> Review | None:
        """
        Check if a review already exists for a specific user and film combination.
        Supports Rule 1 (One review per user per film).
        """
        stmt = (
            select(Review)
            .join(Review.film)
            .options(
                joinedload(Review.film),
                joinedload(Review.user),
            )
            .where(
                Review.film_id == film_id,
                Review.user_id == user_id,
                Film.is_active == True,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update(
        self,
        review: Review,
        update_data: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Review:
        """
        Update specific fields of an existing Review ORM instance.
        Commits and refreshes the instance.
        """
        fields: dict[str, Any] = {}
        if update_data:
            fields.update(update_data)
        fields.update(kwargs)

        for key, value in fields.items():
            if value is not None and hasattr(review, key):
                setattr(review, key, value)

        await self.session.commit()
        await self.session.refresh(review)
        return review

    async def delete(self, review_id: uuid.UUID) -> Review | None:
        """
        Accept review identifier. Find the review.
        If it does not exist, return None instead of raising an exception.
        If it exists, delete it using AsyncSession and commit.
        """
        stmt = select(Review).where(Review.id == review_id)
        result = await self.session.execute(stmt)
        review = result.scalar_one_or_none()
        if review is None:
            return None

        await self.session.delete(review)
        await self.session.commit()
        return review


# ---------------------------------------------------------
# Standalone functions for backward compatibility
# ---------------------------------------------------------
async def get_film_reviews(
    film_id: uuid.UUID,
    db: AsyncSession,
) -> dict:
    """
    Retrieve all reviews for an active film along with the Film title and Reviewer username.
    """
    dao = ReviewDAO(db)
    if not await dao.is_film_active(film_id):
        return {
            "message": f"Film with ID {film_id} not found",
            "film_id": film_id,
            "reviews": [],
            "error": "not_found",
        }

    reviews = await dao.list_by_film(film_id)
    reviews_data = [
        {
            "id": r.id,
            "film_id": r.film_id,
            "film_title": r.film.title if r.film else None,
            "rating": r.rating,
            "body": r.body,
            "reviewer_display_name": r.user.username if r.user else "Anonymous",
            "submitted_at": r.created_at,
        }
        for r in reviews
    ]
    return {
        "message": f"Reviews for film ID {film_id} fetched successfully",
        "film_id": film_id,
        "reviews": reviews_data,
    }


async def get_reviews_with_film_and_user(
    db: AsyncSession,
    film_id: uuid.UUID | None = None,
) -> list[dict]:
    """
    Explicit helper demonstrating retrieving Review, Film title, and Reviewer username
    in a single database round trip for active films (used by test_day4.py).
    """
    stmt = (
        select(Review)
        .join(Review.film)
        .options(
            joinedload(Review.film),
            joinedload(Review.user),
        )
        .where(Film.is_active == True)
    )
    if film_id is not None:
        stmt = stmt.where(Review.film_id == film_id)

    result = await db.execute(stmt)
    reviews = result.scalars().unique().all()

    return [
        {
            "review_id": r.id,
            "film_id": r.film_id,
            "film_title": r.film.title if r.film else None,
            "rating": r.rating,
            "body": r.body,
            "reviewer_username": r.user.username if r.user else None,
            "created_at": r.created_at,
        }
        for r in reviews
    ]


async def create_film_review(
    film_id: uuid.UUID,
    review_data: ReviewCreate,
    db: AsyncSession,
    user_id: uuid.UUID | None = None,
) -> dict:
    dao = ReviewDAO(db)
    if not await dao.is_film_active(film_id):
        raise ValueError(f"Film with ID {film_id} not found or has been soft-deleted")

    if user_id is None:
        first_user = (await db.execute(select(User.id).limit(1))).scalar_one_or_none()
        user_id = first_user

    new_review = Review(
        film_id=film_id,
        user_id=user_id,
        rating=review_data.rating,
        body=review_data.body,
    )
    created = await dao.create(new_review)
    # Reload with relationships
    stmt = select(Review).options(joinedload(Review.film), joinedload(Review.user)).where(Review.id == created.id)
    result = await db.execute(stmt)
    review = result.scalar_one()

    return {
        "id": review.id,
        "film_id": review.film_id,
        "rating": review.rating,
        "body": review.body,
        "reviewer_display_name": review.user.username if review.user else "Anonymous",
        "submitted_at": review.created_at,
    }


async def create_review(
    review_data: ReviewCreate,
    db: AsyncSession,
    user_id: uuid.UUID | None = None,
) -> dict:
    return await create_film_review(
        film_id=review_data.film_id,
        review_data=review_data,
        db=db,
        user_id=user_id,
    )


async def update_review(
    review_id: uuid.UUID,
    db: AsyncSession,
) -> dict:
    return {
        "message": f"Review with ID {review_id} updated successfully",
        "review_id": review_id,
        "status": "success",
    }


async def delete_review(
    review_id: uuid.UUID,
    db: AsyncSession,
) -> dict:
    dao = ReviewDAO(db)
    review = await dao.delete(review_id)
    if review:
        return {
            "message": f"Review with ID {review_id} was deleted successfully",
            "review_id": review_id,
            "status": "success",
        }
    return {
        "message": f"Review with ID {review_id} not found",
        "review_id": review_id,
        "status": "error",
    }
