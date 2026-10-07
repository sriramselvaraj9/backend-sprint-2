import uuid

from fastapi import APIRouter, Depends, Header, Query

from app.dependencies import (
    get_current_user,
    get_review_handler,
    get_review_service,
)
from app.handlers.review_handler import ReviewHandler
from app.schemas.review import ReviewCreate, ReviewResponse, ReviewUpdate
from app.schemas.user import AuthenticatedUser
from app.services.review_service import ReviewService

router = APIRouter(tags=["Reviews"])


@router.get("/films/{film_id}/reviews")
async def get_film_reviews(
    film_id: uuid.UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    review_handler: ReviewHandler = Depends(get_review_handler),
) -> dict:
    """
    Retrieve reviews for a specific active film in a single database round trip.
    Protected endpoint requiring a valid Bearer access token.
    """
    return await review_handler.get_film_reviews(film_id)


@router.post("/films/{film_id}/reviews", response_model=ReviewResponse)
async def create_film_review(
    film_id: uuid.UUID,
    review_data: ReviewCreate,
    current_user: AuthenticatedUser = Depends(get_current_user),
    review_service: ReviewService = Depends(get_review_service),
) -> dict:
    """
    Create a review for a film through the Service layer.
    Protected endpoint requiring a valid Bearer access token.
    Enforces Rule 1: One review per user per film.
    """
    author_id = review_data.user_id if review_data.user_id is not None else current_user.id
    review = await review_service.create_review(
        film_id=film_id,
        review_data=review_data,
        user_id=author_id,
    )
    reviewer_name = review.user.username if review.user else "Anonymous"
    return {
        "id": review.id,
        "film_id": review.film_id,
        "rating": review.rating,
        "body": review.body,
        "reviewer_display_name": reviewer_name,
        "submitted_at": review.created_at,
    }


@router.post("/reviews", response_model=ReviewResponse)
async def create_review(
    review_data: ReviewCreate,
    current_user: AuthenticatedUser = Depends(get_current_user),
    review_service: ReviewService = Depends(get_review_service),
) -> dict:
    """
    Create a review with film_id provided in body.
    Protected endpoint requiring a valid Bearer access token.
    Enforces Rule 1: One review per user per film.
    """
    author_id = review_data.user_id if review_data.user_id is not None else current_user.id
    review = await review_service.create_review(
        film_id=review_data.film_id,
        review_data=review_data,
        user_id=author_id,
    )
    reviewer_name = review.user.username if review.user else "Anonymous"
    return {
        "id": review.id,
        "film_id": review.film_id,
        "rating": review.rating,
        "body": review.body,
        "reviewer_display_name": reviewer_name,
        "submitted_at": review.created_at,
    }


@router.patch("/reviews/{review_id}")
async def update_review(
    review_id: uuid.UUID,
    update_data: ReviewUpdate | None = None,
    user_id: uuid.UUID | None = Query(default=None, description="Current user ID attempting update"),
    x_user_id: str | None = Header(default=None, alias="X-User-ID"),
    current_user: AuthenticatedUser = Depends(get_current_user),
    review_service: ReviewService = Depends(get_review_service),
) -> dict:
    """
    Update a review's rating or body through the Service layer.
    Protected endpoint requiring a valid Bearer access token.
    Enforces Rule 2: Only the original reviewer can update.
    """
    # Resolve user identifier from query, header, body payload, or current_user
    effective_user_id: uuid.UUID | str = (
        user_id
        or x_user_id
        or (update_data.user_id if update_data and update_data.user_id else None)
        or current_user.id
    )

    updated_review = await review_service.update_review(
        review_id=review_id,
        current_user_id=effective_user_id,
        update_data=update_data,
    )
    reviewer_name = updated_review.user.username if updated_review.user else "Anonymous"
    return {
        "message": f"Review with ID {review_id} updated successfully",
        "review_id": str(review_id),
        "status": "success",
        "review": {
            "id": updated_review.id,
            "film_id": updated_review.film_id,
            "rating": updated_review.rating,
            "body": updated_review.body,
            "reviewer_display_name": reviewer_name,
            "submitted_at": updated_review.created_at,
        },
    }


@router.delete("/reviews/{review_id}")
async def delete_review(
    review_id: uuid.UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    review_service: ReviewService = Depends(get_review_service),
) -> dict:
    """
    Delete a review through the Service layer.
    Protected endpoint requiring a valid Bearer access token.
    """
    await review_service.delete_review(review_id)
    return {
        "message": f"Review with ID {review_id} was deleted successfully",
        "review_id": str(review_id),
        "status": "success",
    }
