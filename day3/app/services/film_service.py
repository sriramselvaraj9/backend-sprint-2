from typing import Optional
from app.daos import film_dao
from app.schemas.film import FilmCreate, FilmYearRange


async def get_all_films(genre: Optional[str] = None) -> dict:
    return await film_dao.get_all_films(genre=genre)


async def get_film_by_id(film_id: int) -> dict:
    return await film_dao.get_film_by_id(film_id)


async def create_film(film_data: FilmCreate) -> dict:
    return await film_dao.create_film(film_data)


async def filter_films_by_year_range(year_range: FilmYearRange) -> dict:
    return await film_dao.filter_films_by_year_range(year_range)


async def update_film(film_id: int) -> dict:
    return await film_dao.update_film(film_id)


async def delete_film(film_id: int) -> dict:
    return await film_dao.delete_film(film_id)
