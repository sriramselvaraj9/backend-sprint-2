from sqlalchemy.ext.asyncio import AsyncSession

from app.services import review_service
from app.schemas.review import ReviewCreate


async def handle_get_film_reviews(
    film_id: int,
    db: AsyncSession
) -> dict:
    return await review_service.get_film_reviews(film_id, db=db)


async def handle_create_film_review(
    film_id: int,
    review_data: ReviewCreate,
    db: AsyncSession
) -> dict:
    return await review_service.create_film_review(film_id, review_data, db=db)


async def handle_create_review(
    review_data: ReviewCreate,
    db: AsyncSession
) -> dict:
    return await review_service.create_review(review_data, db=db)


async def handle_update_review(
    review_id: int,
    db: AsyncSession
) -> dict:
    return await review_service.update_review(review_id, db=db)


async def handle_delete_review(
    review_id: int,
    db: AsyncSession
) -> dict:
    return await review_service.delete_review(review_id, db=db)
