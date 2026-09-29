from typing import Optional
from fastapi import APIRouter, Depends
from app.config import Settings
from app.dependencies import get_config, get_db, get_trace_id
from app.handlers import film_handler
from app.schemas.film import FilmCreate, FilmResponse, FilmYearRange

router = APIRouter(tags=["Films"])


@router.get("/films")
async def get_films(
    genre: Optional[str] = None,
    config: Settings = Depends(get_config),
    db: str = Depends(get_db),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    """
    Retrieve all films with optional genre filter.
    Declares all three shared dependencies: config, db, and trace_id.
    """
    films_data = await film_handler.handle_get_all_films(genre=genre)
    return {
        "message": "Films retrieved successfully",
        "api_version": config.API_VERSION,
        "trace_id": trace_id,
        "database": db,
        "db_session": db,
        "data": films_data.get("films", films_data),
    }


@router.get("/films/{film_id}")
async def get_film(
    film_id: int,
    config: Settings = Depends(get_config),
    db: str = Depends(get_db),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    """
    Retrieve a single film by ID.
    Declares all three shared dependencies: config, db, and trace_id.
    """
    film_data = await film_handler.handle_get_film_by_id(film_id)
    return {
        "message": film_data.get("message", "Film retrieved successfully"),
        "api_version": config.API_VERSION,
        "trace_id": trace_id,
        "database": db,
        "db_session": db,
        "data": film_data.get("film", film_data),
    }


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
