from sqlalchemy.ext.asyncio import AsyncSession

from app.services import film_service
from app.schemas.film import FilmCreate, FilmYearRange


async def handle_get_all_films(
    db: AsyncSession,
    genre: str | None = None
) -> dict:
    return await film_service.get_all_films(db=db, genre=genre)


async def handle_get_film_by_id(
    film_id: int,
    db: AsyncSession
) -> dict:
    return await film_service.get_film_by_id(film_id, db=db)


async def handle_create_film(
    film_data: FilmCreate,
    db: AsyncSession
) -> dict:
    film_dict = film_data.model_dump()
    film_json = film_data.model_dump_json()
    print(f"[DEBUG] Validated FilmCreate as dict: {film_dict}")
    print(f"[DEBUG] Validated FilmCreate as JSON: {film_json}")
    return await film_service.create_film(film_data, db=db)


async def handle_filter_films_by_year_range(
    year_range: FilmYearRange,
    db: AsyncSession
) -> dict:
    range_dict = year_range.model_dump()
    print(f"[DEBUG] Validated FilmYearRange: {range_dict}")
    return await film_service.filter_films_by_year_range(year_range, db=db)


async def handle_update_film(
    film_id: int,
    db: AsyncSession
) -> dict:
    return await film_service.update_film(film_id, db=db)


async def handle_delete_film(
    film_id: int,
    db: AsyncSession
) -> dict:
    return await film_service.delete_film(film_id, db=db)
