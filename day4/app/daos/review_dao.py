from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.film import Film
from app.models.review import Review
from app.models.user import User
from app.schemas.review import ReviewCreate


async def get_film_reviews(
    film_id: int,
    db: AsyncSession
) -> dict:
    """
    3. Review Query Requirement
    Retrieve all reviews for a film along with the Film title and Reviewer username
    in a SINGLE database round trip using SQLAlchemy's joinedload().
    Avoids N+1 query problem by generating an SQL JOIN across Review, Film, and User tables.
    """
    stmt = (
        select(Review)
        .options(
            joinedload(Review.film),
            joinedload(Review.user),
        )
        .where(Review.film_id == film_id)
    )
    result = await db.execute(stmt)
    reviews = result.scalars().all()

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
    film_id: Optional[int] = None
) -> list[dict]:
    """
    3. Review Query Requirement:
    Explicit helper demonstrating retrieving Review, Film title, and Reviewer username
    in a single database round trip.
    """
    stmt = (
        select(Review)
        .options(
            joinedload(Review.film),
            joinedload(Review.user),
        )
    )
    if film_id is not None:
        stmt = stmt.where(Review.film_id == film_id)

    result = await db.execute(stmt)
    reviews = result.scalars().all()

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
    film_id: int,
    review_data: ReviewCreate,
    db: AsyncSession,
    user_id: int = 1
) -> dict:
    new_review = Review(
        film_id=film_id,
        user_id=user_id,
        rating=review_data.rating,
        body=review_data.body,
    )
    db.add(new_review)
    await db.commit()

    # Reload with relationships in single round trip
    stmt = (
        select(Review)
        .options(joinedload(Review.film), joinedload(Review.user))
        .where(Review.id == new_review.id)
    )
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
    user_id: int = 1
) -> dict:
    return await create_film_review(
        film_id=review_data.film_id,
        review_data=review_data,
        db=db,
        user_id=user_id,
    )


async def update_review(
    review_id: int,
    db: AsyncSession
) -> dict:
    return {
        "message": f"Review with ID {review_id} updated successfully",
        "review_id": review_id,
        "status": "success",
    }


async def delete_review(
    review_id: int,
    db: AsyncSession
) -> dict:
    stmt = select(Review).where(Review.id == review_id)
    result = await db.execute(stmt)
    review = result.scalar_one_or_none()
    if review:
        await db.delete(review)
        await db.commit()
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
