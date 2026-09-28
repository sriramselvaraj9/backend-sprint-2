from fastapi import APIRouter
from app.handlers import film_handler
from app.schemas.film import FilmCreate, FilmResponse

router = APIRouter(tags=["Films"])


@router.get("/films")
async def get_films() -> dict:
    return await film_handler.handle_get_all_films()


@router.get("/films/{film_id}")
async def get_film(film_id: int) -> dict:
    return await film_handler.handle_get_film_by_id(film_id)


@router.post("/films", response_model=FilmResponse)
async def create_film(film_data: FilmCreate) -> dict:
    return await film_handler.handle_create_film(film_data)


@router.patch("/films/{film_id}")
async def update_film(film_id: int) -> dict:
    return await film_handler.handle_update_film(film_id)


@router.delete("/films/{film_id}")
async def delete_film(film_id: int) -> dict:
    return await film_handler.handle_delete_film(film_id)
