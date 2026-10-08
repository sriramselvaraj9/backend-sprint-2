import uuid

from fastapi import APIRouter, Depends, Header, Query

from app.dependencies import (
    get_current_user,
    get_review_handler,
    require_role,
)
from app.handlers.review_handler import ReviewHandler
from app.schemas.review import ReviewCreate, ReviewResponse, ReviewUpdate
from app.schemas.user import AuthenticatedUser

router = APIRouter(tags=["Reviews"])


@router.get("/films/{film_id}/reviews")
async def get_film_reviews(
    film_id: uuid.UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    review_handler: ReviewHandler = Depends(get_review_handler),
) -> dict:
    """
    Retrieve reviews for a specific active film in a single database round trip.
    Accessible to Admin, Critic, and Viewer.
    """
    return await review_handler.get_film_reviews(film_id)


@router.post("/films/{film_id}/reviews", response_model=ReviewResponse)
async def create_film_review(
    film_id: uuid.UUID,
    review_data: ReviewCreate,
    current_user: AuthenticatedUser = Depends(require_role("admin", "critic")),
    review_handler: ReviewHandler = Depends(get_review_handler),
) -> dict:
    """
    Create a review for a film through the Handler layer.
    Admin and Critic only: Viewers are forbidden.
    Enforces Rule 1: One review per user per film.
    """
    author_id = review_data.user_id if review_data.user_id is not None else current_user.id
    return await review_handler.create_film_review(
        film_id=film_id,
        review_data=review_data,
        user_id=author_id,
    )


@router.post("/reviews", response_model=ReviewResponse)
async def create_review(
    review_data: ReviewCreate,
    current_user: AuthenticatedUser = Depends(require_role("admin", "critic")),
    review_handler: ReviewHandler = Depends(get_review_handler),
) -> dict:
    """
    Create a review with film_id provided in body.
    Admin and Critic only: Viewers are forbidden.
    Enforces Rule 1: One review per user per film.
    """
    author_id = review_data.user_id if review_data.user_id is not None else current_user.id
    return await review_handler.create_film_review(
        film_id=review_data.film_id,
        review_data=review_data,
        user_id=author_id,
    )


@router.patch("/reviews/{review_id}")
async def update_review(
    review_id: uuid.UUID,
    update_data: ReviewUpdate | None = None,
    user_id: uuid.UUID | None = Query(default=None, description="Current user ID attempting update"),
    x_user_id: str | None = Header(default=None, alias="X-User-ID"),
    current_user: AuthenticatedUser = Depends(require_role("admin", "critic")),
    review_handler: ReviewHandler = Depends(get_review_handler),
) -> dict:
    """
    Update a review's rating or body through the Handler layer.
    Admin and Critic only: Viewers are forbidden.
    Enforces Rule 2: Critics can only update their own reviews; Admins can update any review.
    """
    effective_user_id: uuid.UUID | str = (
        user_id
        or x_user_id
        or (update_data.user_id if update_data and update_data.user_id else None)
        or current_user.id
    )
    is_admin = (current_user.role or "").lower() == "admin"
    return await review_handler.update_review(
        review_id=review_id,
        update_data=update_data,
        current_user_id=effective_user_id,
        is_admin=is_admin,
    )


@router.delete("/reviews/{review_id}")
async def delete_review(
    review_id: uuid.UUID,
    current_user: AuthenticatedUser = Depends(require_role("admin", "critic")),
    review_handler: ReviewHandler = Depends(get_review_handler),
) -> dict:
    """
    Delete a review through the Handler layer.
    Admin and Critic only: Viewers are forbidden.
    Enforces Rule: Critics can only delete their own reviews; Admins can delete any review.
    """
    is_admin = (current_user.role or "").lower() == "admin"
    return await review_handler.delete_review(
        review_id=review_id,
        current_user_id=current_user.id,
        is_admin=is_admin,
    )
