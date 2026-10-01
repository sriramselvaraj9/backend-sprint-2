from sqlalchemy.ext.asyncio import AsyncSession

from app.daos import review_dao
from app.schemas.review import ReviewCreate


async def get_film_reviews(
    film_id: int,
    db: AsyncSession
) -> dict:
    return await review_dao.get_film_reviews(film_id, db=db)


async def create_film_review(
    film_id: int,
    review_data: ReviewCreate,
    db: AsyncSession
) -> dict:
    return await review_dao.create_film_review(film_id, review_data, db=db)


async def create_review(
    review_data: ReviewCreate,
    db: AsyncSession
) -> dict:
    return await review_dao.create_review(review_data, db=db)


async def update_review(
    review_id: int,
    db: AsyncSession
) -> dict:
    return await review_dao.update_review(review_id, db=db)


async def delete_review(
    review_id: int,
    db: AsyncSession
) -> dict:
    return await review_dao.delete_review(review_id, db=db)
