import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.daos.film_dao import FilmDAO
from app.daos.review_dao import ReviewDAO
from app.daos.user_dao import UserDAO
from app.exceptions.domain import (
    FilmNotFoundError,
    ReviewAlreadyExistsError,
    ReviewNotFoundError,
    ReviewUnauthorisedError,
    UserNotFoundError,
)
from app.models.review import Review
from app.schemas.review import ReviewCreate, ReviewUpdate

logger = logging.getLogger("review_service")


class ReviewService:
    """
    Service layer for Review business operations.
    Coordinates ReviewDAO, FilmDAO, and UserDAO to enforce business rules:
    1. One review per user per film.
    2. Only the original reviewer can update a review.
    Contains NO direct database queries or session executions.
    """

    def __init__(
        self,
        review_dao: ReviewDAO,
        film_dao: FilmDAO | None = None,
        user_dao: UserDAO | None = None,
    ) -> None:
        self.review_dao = review_dao
        self.film_dao = film_dao if film_dao is not None else FilmDAO(review_dao.session)
        self.user_dao = user_dao if user_dao is not None else UserDAO(review_dao.session)
        # Compatibility alias
        self.dao = self.review_dao

    async def is_film_active(self, film_id: uuid.UUID | str) -> bool:
        """
        Check if film exists and is active through the DAO.
        """
        return await self.review_dao.is_film_active(uuid.UUID(str(film_id)))

    async def get_film_reviews(self, film_id: uuid.UUID | str) -> list[Review]:
        """
        Retrieve all reviews for an active film through ReviewDAO.
        Raises FilmNotFoundError if film is not active or does not exist.
        """
        uid = uuid.UUID(str(film_id))
        logger.info(f"Fetching reviews for film {uid}")
        if not await self.review_dao.is_film_active(uid):
            logger.warning(f"Cannot get reviews: Film {uid} not found or inactive")
            raise FilmNotFoundError(film_id=uid)
        return await self.review_dao.list_by_film(uid)

    async def get_average_rating(self, film_id: uuid.UUID | str) -> float | None:
        """
        Compute average rating for a film through ReviewDAO.
        """
        uid = uuid.UUID(str(film_id))
        return await self.review_dao.average_rating(uid)

    async def create_review(
        self,
        film_id: uuid.UUID | str,
        review_data: ReviewCreate,
        user_id: uuid.UUID | str | None = None,
    ) -> Review:
        """
        Create a new review enforcing Rule 1: One review per user per film.
        """
        target_film_id = uuid.UUID(str(film_id))

        # 1. Verify that the referenced film exists and is active
        if not await self.review_dao.is_film_active(target_film_id):
            logger.warning(f"Review creation rejected: Film {target_film_id} not found or inactive")
            raise FilmNotFoundError(film_id=target_film_id)

        # 2. Resolve reviewer user ID
        resolved_user_id: uuid.UUID
        if user_id is not None:
            resolved_user_id = uuid.UUID(str(user_id))
        elif review_data.user_id is not None:
            resolved_user_id = uuid.UUID(str(review_data.user_id))
        else:
            default_user = await self.user_dao.get_default_user()
            if default_user is None:
                raise UserNotFoundError(user_id="default_user", message="No active user available to author review")
            resolved_user_id = default_user.id

        logger.info(f"Creating review for film {target_film_id} by user {resolved_user_id}")

        # 3. Rule 1 Check: Check whether the user already reviewed the film
        logger.info(f"Checking whether user {resolved_user_id} already reviewed film {target_film_id}")
        existing_review = await self.review_dao.get_by_film_and_user(
            film_id=target_film_id,
            user_id=resolved_user_id,
        )

        if existing_review is not None:
            logger.warning(f"Review creation rejected: user {resolved_user_id} already reviewed film {target_film_id}")
            raise ReviewAlreadyExistsError(
                film_id=target_film_id,
                user_id=resolved_user_id,
            )

        # 4. Create and persist review via DAO
        new_review = Review(
            film_id=target_film_id,
            user_id=resolved_user_id,
            rating=review_data.rating,
            body=review_data.body,
        )

        created_review = await self.review_dao.create(new_review)
        logger.info(f"Review created successfully with ID {created_review.id}")
        return created_review

    async def update_review(
        self,
        review_id: uuid.UUID | str,
        current_user_id: uuid.UUID | str | None = None,
        rating: int | None = None,
        body: str | None = None,
        update_data: ReviewUpdate | dict[str, Any] | None = None,
    ) -> Review:
        """
        Update a review enforcing Rule 2: Only the original reviewer can update.
        """
        target_review_id = uuid.UUID(str(review_id))
        logger.info(f"Attempting to update review {target_review_id}")

        # 1. Fetch the review via DAO
        review = await self.review_dao.get_by_id(target_review_id)
        if review is None:
            logger.warning(f"Review update failed: Review {target_review_id} not found")
            raise ReviewNotFoundError(review_id=target_review_id)

        # 2. Resolve current user performing the update
        caller_id: uuid.UUID | None = None
        if current_user_id is not None:
            caller_id = uuid.UUID(str(current_user_id))
        elif isinstance(update_data, ReviewUpdate) and update_data.user_id is not None:
            caller_id = update_data.user_id
        elif isinstance(update_data, dict) and update_data.get("user_id") is not None:
            caller_id = uuid.UUID(str(update_data["user_id"]))

        # 3. Rule 2 Check: Compare current user ID with review.user_id
        if caller_id is not None and str(caller_id) != str(review.user_id):
            logger.warning(
                f"Review update rejected: user {caller_id} is not original reviewer of review {target_review_id}"
            )
            raise ReviewUnauthorisedError(
                review_id=target_review_id,
                user_id=caller_id,
            )

        # 4. Extract fields to update
        updates: dict[str, Any] = {}
        if rating is not None:
            updates["rating"] = rating
        if body is not None:
            updates["body"] = body

        if isinstance(update_data, ReviewUpdate):
            if update_data.rating is not None:
                updates["rating"] = update_data.rating
            if update_data.body is not None:
                updates["body"] = update_data.body
        elif isinstance(update_data, dict):
            if "rating" in update_data and update_data["rating"] is not None:
                updates["rating"] = update_data["rating"]
            if "body" in update_data and update_data["body"] is not None:
                updates["body"] = update_data["body"]

        # 5. Persist updates through ReviewDAO
        updated_review = await self.review_dao.update(review, update_data=updates)
        logger.info(f"Review {target_review_id} updated successfully")
        return updated_review

    async def delete_review(
        self,
        review_id: uuid.UUID | str,
        current_user_id: uuid.UUID | str | None = None,
    ) -> Review:
        """
        Delete a review by ID through ReviewDAO.
        """
        target_review_id = uuid.UUID(str(review_id))
        logger.info(f"Deleting review {target_review_id}")

        review = await self.review_dao.get_by_id(target_review_id)
        if review is None:
            logger.warning(f"Review deletion failed: Review {target_review_id} not found")
            raise ReviewNotFoundError(review_id=target_review_id)

        if current_user_id is not None:
            caller_id = uuid.UUID(str(current_user_id))
            if str(caller_id) != str(review.user_id):
                raise ReviewUnauthorisedError(
                    review_id=target_review_id,
                    user_id=caller_id,
                )

        deleted = await self.review_dao.delete(target_review_id)
        if deleted is None:
            raise ReviewNotFoundError(review_id=target_review_id)

        logger.info(f"Review {target_review_id} deleted successfully")
        return deleted


# ---------------------------------------------------------
# Standalone functions for backward compatibility
# ---------------------------------------------------------
async def get_film_reviews(film_id: uuid.UUID, db: AsyncSession) -> dict:
    from app.daos import review_dao

    return await review_dao.get_film_reviews(film_id, db=db)


async def create_film_review(
    film_id: uuid.UUID,
    review_data: ReviewCreate,
    db: AsyncSession,
    user_id: uuid.UUID | None = None,
) -> dict:
    from app.daos import review_dao

    return await review_dao.create_film_review(film_id, review_data, db=db, user_id=user_id)


async def create_review(
    review_data: ReviewCreate,
    db: AsyncSession,
    user_id: uuid.UUID | None = None,
) -> dict:
    from app.daos import review_dao

    return await review_dao.create_review(review_data, db=db, user_id=user_id)


async def update_review(review_id: uuid.UUID, db: AsyncSession) -> dict:
    from app.daos import review_dao

    return await review_dao.update_review(review_id, db=db)


async def delete_review(review_id: uuid.UUID, db: AsyncSession) -> dict:
    from app.daos import review_dao

    return await review_dao.delete_review(review_id, db=db)
