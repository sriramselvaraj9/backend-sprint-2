from app.services import film_service
from app.schemas.film import FilmCreate


async def handle_get_all_films() -> dict:
    return await film_service.get_all_films()


async def handle_get_film_by_id(film_id: int) -> dict:
    return await film_service.get_film_by_id(film_id)


async def handle_create_film(film_data: FilmCreate) -> dict:
    return await film_service.create_film(film_data)


async def handle_update_film(film_id: int) -> dict:
    return await film_service.update_film(film_id)


async def handle_delete_film(film_id: int) -> dict:
    return await film_service.delete_film(film_id)
