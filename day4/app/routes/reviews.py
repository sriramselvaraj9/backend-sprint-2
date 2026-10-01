from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.handlers import review_handler
from app.schemas.review import ReviewCreate, ReviewResponse

router = APIRouter(tags=["Reviews"])


@router.get("/films/{film_id}/reviews")
async def get_film_reviews(
    film_id: int,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Retrieve reviews for a specific film in a single database round trip.
    """
    return await review_handler.handle_get_film_reviews(film_id, db=db)


@router.post("/films/{film_id}/reviews", response_model=ReviewResponse)
async def create_film_review(
    film_id: int,
    review_data: ReviewCreate,
    db: AsyncSession = Depends(get_db)
) -> dict:
    return await review_handler.handle_create_film_review(film_id, review_data, db=db)


@router.post("/reviews", response_model=ReviewResponse)
async def create_review(
    review_data: ReviewCreate,
    db: AsyncSession = Depends(get_db)
) -> dict:
    return await review_handler.handle_create_review(review_data, db=db)


@router.patch("/reviews/{review_id}")
async def update_review(
    review_id: int,
    db: AsyncSession = Depends(get_db)
) -> dict:
    return await review_handler.handle_update_review(review_id, db=db)


@router.delete("/reviews/{review_id}")
async def delete_review(
    review_id: int,
    db: AsyncSession = Depends(get_db)
) -> dict:
    return await review_handler.handle_delete_review(review_id, db=db)
