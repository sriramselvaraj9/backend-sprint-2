import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.daos.film_dao import FilmDAO
from app.daos.review_dao import ReviewDAO
from app.daos.user_dao import UserDAO
from app.schemas.review import ReviewCreate, ReviewUpdate
from app.services.review_service import ReviewService


class ReviewHandler:
    """
    Handler layer for Review requests.
    Translates HTTP layer requests to Service operations and formats responses.
    Contains NO direct database queries or business logic.
    """

    def __init__(self, service: ReviewService) -> None:
        self.service = service

    async def get_film_reviews(self, film_id: uuid.UUID | str) -> dict:
        uid = uuid.UUID(str(film_id))
        reviews = await self.service.get_film_reviews(uid)
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
            "film_id": str(film_id),
            "reviews": reviews_data,
        }

    async def create_film_review(
        self,
        film_id: uuid.UUID | str,
        review_data: ReviewCreate,
        user_id: uuid.UUID | str | None = None,
    ) -> dict:
        review = await self.service.create_review(film_id, review_data, user_id=user_id)
        reviewer_name = review.user.username if review.user else "Anonymous"
        return {
            "id": review.id,
            "film_id": review.film_id,
            "rating": review.rating,
            "body": review.body,
            "reviewer_display_name": reviewer_name,
            "submitted_at": review.created_at,
        }

    async def update_review(
        self,
        review_id: uuid.UUID | str,
        update_data: ReviewUpdate | dict[str, Any] | None = None,
        current_user_id: uuid.UUID | str | None = None,
        is_admin: bool = False,
    ) -> dict:
        updated = await self.service.update_review(
            review_id=review_id,
            current_user_id=current_user_id,
            update_data=update_data,
            is_admin=is_admin,
        )
        return {
            "message": f"Review with ID {review_id} updated successfully",
            "review_id": str(review_id),
            "status": "success",
            "review": {
                "id": updated.id,
                "film_id": updated.film_id,
                "rating": updated.rating,
                "body": updated.body,
                "reviewer_display_name": updated.user.username if updated.user else "Anonymous",
                "submitted_at": updated.created_at,
            },
        }

    async def delete_review(
        self,
        review_id: uuid.UUID | str,
        current_user_id: uuid.UUID | str | None = None,
        is_admin: bool = False,
    ) -> dict:
        await self.service.delete_review(
            review_id=review_id,
            current_user_id=current_user_id,
            is_admin=is_admin,
        )
        return {
            "message": f"Review with ID {review_id} was deleted successfully",
            "review_id": str(review_id),
            "status": "success",
        }


# ---------------------------------------------------------
# Standalone functions for backward compatibility
# ---------------------------------------------------------
async def handle_get_film_reviews(film_id: uuid.UUID, db: AsyncSession) -> dict:
    service = ReviewService(ReviewDAO(db), FilmDAO(db), UserDAO(db))
    handler = ReviewHandler(service)
    return await handler.get_film_reviews(film_id)


async def handle_create_film_review(
    film_id: uuid.UUID,
    review_data: ReviewCreate,
    db: AsyncSession,
) -> dict:
    service = ReviewService(ReviewDAO(db), FilmDAO(db), UserDAO(db))
    handler = ReviewHandler(service)
    return await handler.create_film_review(film_id, review_data)


async def handle_create_review(
    review_data: ReviewCreate,
    db: AsyncSession,
) -> dict:
    service = ReviewService(ReviewDAO(db), FilmDAO(db), UserDAO(db))
    handler = ReviewHandler(service)
    return await handler.create_film_review(review_data.film_id, review_data)


async def handle_update_review(review_id: uuid.UUID, db: AsyncSession) -> dict:
    service = ReviewService(ReviewDAO(db), FilmDAO(db), UserDAO(db))
    handler = ReviewHandler(service)
    return await handler.update_review(review_id)


async def handle_delete_review(review_id: uuid.UUID, db: AsyncSession) -> dict:
    service = ReviewService(ReviewDAO(db), FilmDAO(db), UserDAO(db))
    handler = ReviewHandler(service)
    return await handler.delete_review(review_id)
