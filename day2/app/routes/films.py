from fastapi import APIRouter
from app.handlers import film_handler
from app.schemas.film import FilmCreate, FilmResponse, FilmYearRange

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


@router.post("/films/filter/year-range", response_model=dict)
async def filter_films_by_year_range(year_range: FilmYearRange) -> dict:
    """
    Endpoint demonstrating @model_validator(mode="after") with start_year < end_year.
    """
    return await film_handler.handle_filter_films_by_year_range(year_range)


@router.patch("/films/{film_id}")
async def update_film(film_id: int) -> dict:
    return await film_handler.handle_update_film(film_id)


@router.delete("/films/{film_id}")
async def delete_film(film_id: int) -> dict:
    return await film_handler.handle_delete_film(film_id)
