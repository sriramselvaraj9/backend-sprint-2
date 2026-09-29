from fastapi import APIRouter
from app.handlers import review_handler
from app.schemas.review import ReviewCreate, ReviewResponse

router = APIRouter(tags=["Reviews"])


@router.get("/films/{film_id}/reviews")
async def get_film_reviews(film_id: int) -> dict:
    return await review_handler.handle_get_film_reviews(film_id)


@router.post("/films/{film_id}/reviews", response_model=ReviewResponse)
async def create_film_review(film_id: int, review_data: ReviewCreate) -> dict:
    return await review_handler.handle_create_film_review(film_id, review_data)


@router.post("/reviews", response_model=ReviewResponse)
async def create_review(review_data: ReviewCreate) -> dict:
    return await review_handler.handle_create_review(review_data)


@router.patch("/reviews/{review_id}")
async def update_review(review_id: int) -> dict:
    return await review_handler.handle_update_review(review_id)


@router.delete("/reviews/{review_id}")
async def delete_review(review_id: int) -> dict:
    return await review_handler.handle_delete_review(review_id)
