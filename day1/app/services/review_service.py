from app.daos import review_dao
from app.schemas.review import ReviewCreate


async def get_film_reviews(film_id: int) -> dict:
    return await review_dao.get_film_reviews(film_id)


async def create_film_review(film_id: int, review_data: ReviewCreate) -> dict:
    return await review_dao.create_film_review(film_id, review_data)


async def update_review(review_id: int) -> dict:
    return await review_dao.update_review(review_id)


async def delete_review(review_id: int) -> dict:
    return await review_dao.delete_review(review_id)
