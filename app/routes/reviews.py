import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Query, Request

from app.dependencies import (
    get_current_user,
    get_review_handler,
    require_role,
)
from app.handlers.review_handler import ReviewHandler
from app.logging_config import get_request_id
from app.schemas.common import PaginationParams
from app.schemas.review import ReviewCreate, ReviewResponse, ReviewUpdate
from app.schemas.user import AuthenticatedUser
from app.services.film_service import recalculate_film_review_aggregates

router = APIRouter(tags=["Reviews"])


@router.get("/films/{film_id}/reviews")
async def get_film_reviews(
    film_id: uuid.UUID,
    pagination: PaginationParams = Depends(),
    current_user: AuthenticatedUser = Depends(get_current_user),
    review_handler: ReviewHandler = Depends(get_review_handler),
) -> dict:
    """
    Retrieve reviews for a specific active film in a single database round trip.
    Supports offset-based pagination (page, page_size).
    Accessible to Admin, Critic, and Viewer.
    """
    return await review_handler.get_film_reviews(
        film_id=film_id,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.post("/films/{film_id}/reviews", response_model=ReviewResponse)
async def create_film_review(
    film_id: uuid.UUID,
    review_data: ReviewCreate,
    background_tasks: BackgroundTasks,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role("admin", "critic")),
    review_handler: ReviewHandler = Depends(get_review_handler),
) -> dict:
    """
    Create a review for a film through the Handler layer.
    Admin and Critic only: Viewers are forbidden.
    Enforces Rule 1: One review per user per film.
    After successful commit, schedules background aggregate recalculation.
    """
    author_id = review_data.user_id if review_data.user_id is not None else current_user.id
    result = await review_handler.create_film_review(  # 1. Create and commit the review to PostgreSQL
        film_id=film_id,
        review_data=review_data,
        user_id=author_id,
    )
    # 2. Get trace ID from request state
    request_id = getattr(request.state, "request_id", None) or get_request_id()
    # 3. Schedule background recalculation
    background_tasks.add_task(recalculate_film_review_aggregates, film_id=film_id, request_id=request_id)
    return result


@router.post("/reviews", response_model=ReviewResponse)
async def create_review(
    review_data: ReviewCreate,
    background_tasks: BackgroundTasks,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role("admin", "critic")),
    review_handler: ReviewHandler = Depends(get_review_handler),
) -> dict:
    """
    Create a review with film_id provided in body.
    Admin and Critic only: Viewers are forbidden.
    Enforces Rule 1: One review per user per film.
    After successful commit, schedules background aggregate recalculation.
    """
    author_id = review_data.user_id if review_data.user_id is not None else current_user.id
    target_film_id = review_data.film_id
    result = await review_handler.create_film_review(
        film_id=target_film_id,
        review_data=review_data,
        user_id=author_id,
    )
    request_id = getattr(request.state, "request_id", None) or get_request_id()
    background_tasks.add_task(recalculate_film_review_aggregates, film_id=target_film_id, request_id=request_id)
    return result


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
