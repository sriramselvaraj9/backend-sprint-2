from app.daos import film_dao
from app.schemas.film import FilmCreate


async def get_all_films() -> dict:
    return await film_dao.get_all_films()


async def get_film_by_id(film_id: int) -> dict:
    return await film_dao.get_film_by_id(film_id)


async def create_film(film_data: FilmCreate) -> dict:
    return await film_dao.create_film(film_data)


async def update_film(film_id: int) -> dict:
    return await film_dao.update_film(film_id)


async def delete_film(film_id: int) -> dict:
    return await film_dao.delete_film(film_id)
