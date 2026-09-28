from app.services import review_service
from app.schemas.review import ReviewCreate


async def handle_get_film_reviews(film_id: int) -> dict:
    return await review_service.get_film_reviews(film_id)


async def handle_create_film_review(film_id: int, review_data: ReviewCreate) -> dict:
    return await review_service.create_film_review(film_id, review_data)


async def handle_update_review(review_id: int) -> dict:
    return await review_service.update_review(review_id)


async def handle_delete_review(review_id: int) -> dict:
    return await review_service.delete_review(review_id)
