from sqlalchemy.ext.asyncio import AsyncSession

from app.daos import film_dao
from app.schemas.film import FilmCreate, FilmYearRange


async def get_all_films(
    db: AsyncSession,
    genre: str | None = None
) -> dict:
    return await film_dao.get_all_films(db=db, genre=genre)


async def get_film_by_id(
    film_id: int,
    db: AsyncSession
) -> dict:
    return await film_dao.get_film_by_id(film_id, db=db)


async def create_film(
    film_data: FilmCreate,
    db: AsyncSession
) -> dict:
    return await film_dao.create_film(film_data, db=db)


async def filter_films_by_year_range(
    year_range: FilmYearRange,
    db: AsyncSession
) -> dict:
    return await film_dao.filter_films_by_year_range(year_range, db=db)


async def update_film(
    film_id: int,
    db: AsyncSession
) -> dict:
    return await film_dao.update_film(film_id, db=db)


async def delete_film(
    film_id: int,
    db: AsyncSession
) -> dict:
    return await film_dao.delete_film(film_id, db=db)
