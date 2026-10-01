from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.dependencies import get_config, get_db, get_trace_id
from app.handlers import film_handler
from app.schemas.film import FilmCreate, FilmResponse, FilmYearRange

router = APIRouter(tags=["Films"])


@router.get("/films")
async def get_films(
    genre: str | None = None,
    config: Settings = Depends(get_config),
    db: AsyncSession = Depends(get_db),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    """
    7. Real Database Read
    Retrieve all films with optional genre filter directly from PostgreSQL.
    Maintains the exact Day 3 signature: config, db (AsyncSession), and trace_id.
    """
    films_data = await film_handler.handle_get_all_films(genre=genre, db=db)
    return {
        "message": "Films retrieved successfully",
        "api_version": config.API_VERSION,
        "trace_id": trace_id,
        "database": "postgresql+asyncpg",
        "db_session": "active",
        "data": films_data.get("films", films_data),
    }


@router.get("/films/{film_id}")
async def get_film(
    film_id: int,
    config: Settings = Depends(get_config),
    db: AsyncSession = Depends(get_db),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    """
    Retrieve a single film by ID from PostgreSQL.
    Maintains the exact Day 3 signature: config, db (AsyncSession), and trace_id.
    """
    film_data = await film_handler.handle_get_film_by_id(film_id, db=db)
    return {
        "message": film_data.get("message", "Film retrieved successfully"),
        "api_version": config.API_VERSION,
        "trace_id": trace_id,
        "database": "postgresql+asyncpg",
        "db_session": "active",
        "data": film_data.get("film", film_data),
    }


@router.post("/films", response_model=FilmResponse)
async def create_film(
    film_data: FilmCreate,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Create a new film in PostgreSQL and return with Day 2 FilmResponse schema.
    """
    return await film_handler.handle_create_film(film_data, db=db)


@router.post("/films/filter/year-range", response_model=dict)
async def filter_films_by_year_range(
    year_range: FilmYearRange,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Endpoint demonstrating @model_validator(mode="after") with start_year < end_year.
    """
    return await film_handler.handle_filter_films_by_year_range(year_range, db=db)


@router.patch("/films/{film_id}")
async def update_film(
    film_id: int,
    db: AsyncSession = Depends(get_db)
) -> dict:
    return await film_handler.handle_update_film(film_id, db=db)


@router.delete("/films/{film_id}")
async def delete_film(
    film_id: int,
    db: AsyncSession = Depends(get_db)
) -> dict:
    return await film_handler.handle_delete_film(film_id, db=db)
