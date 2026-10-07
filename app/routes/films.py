import uuid

from fastapi import APIRouter, Depends

from app.config import Settings
from app.dependencies import (
    get_config,
    get_current_user,
    get_film_handler,
    get_film_service,
    get_trace_id,
)
from app.handlers.film_handler import FilmHandler
from app.schemas.film import FilmCreate, FilmResponse, FilmYearRange
from app.schemas.user import AuthenticatedUser
from app.services.film_service import FilmService

router = APIRouter(tags=["Films"])


@router.get("/films")
async def get_films(
    genre: str | None = None,
    current_user: AuthenticatedUser = Depends(get_current_user),
    config: Settings = Depends(get_config),
    film_handler: FilmHandler = Depends(get_film_handler),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    """
    Retrieve all active films with optional genre filter.
    Protected endpoint requiring a valid Bearer access token.
    Layered flow: Route -> Handler -> Service -> DAO -> Database.
    """
    films_data = await film_handler.get_all_films(genre=genre)
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
    film_id: uuid.UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    config: Settings = Depends(get_config),
    film_service: FilmService = Depends(get_film_service),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    """
    Retrieve a single active film by ID.
    Protected endpoint requiring a valid Bearer access token.
    """
    film = await film_service.get_film_by_id(film_id)
    return {
        "message": f"Film with ID {film_id} fetched successfully",
        "api_version": config.API_VERSION,
        "trace_id": trace_id,
        "database": "postgresql+asyncpg",
        "db_session": "active",
        "data": FilmResponse.model_validate(film).model_dump(),
    }


@router.post("/films", response_model=FilmResponse)
async def create_film(
    film_data: FilmCreate,
    current_user: AuthenticatedUser = Depends(get_current_user),
    film_service: FilmService = Depends(get_film_service),
) -> FilmResponse:
    """
    Create a new film through the Service layer.
    Protected endpoint requiring a valid Bearer access token.
    """
    film = await film_service.create_film(film_data)
    return FilmResponse.model_validate(film)


@router.post("/films/filter/year-range", response_model=dict)
async def filter_films_by_year_range(
    year_range: FilmYearRange,
    current_user: AuthenticatedUser = Depends(get_current_user),
    film_handler: FilmHandler = Depends(get_film_handler),
) -> dict:
    """
    Endpoint demonstrating @model_validator(mode="after") with start_year < end_year.
    Protected endpoint requiring a valid Bearer access token.
    """
    return await film_handler.filter_films_by_year_range(year_range)


@router.patch("/films/{film_id}")
async def update_film(
    film_id: uuid.UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    film_service: FilmService = Depends(get_film_service),
) -> dict:
    """
    Update film attributes through the Service layer.
    Protected endpoint requiring a valid Bearer access token.
    """
    film = await film_service.update_film(film_id)
    return {
        "message": f"Film with ID {film_id} updated successfully",
        "film_id": str(film_id),
        "status": "success",
        "film": FilmResponse.model_validate(film).model_dump(),
    }


@router.delete("/films/{film_id}")
async def delete_film(
    film_id: uuid.UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    film_service: FilmService = Depends(get_film_service),
) -> dict:
    """
    Soft-delete film enforcing the business rule in FilmService:
    Film cannot be soft-deleted if active reviews exist.
    Protected endpoint requiring a valid Bearer access token.
    """
    await film_service.delete_film(film_id)
    return {
        "message": f"Film with ID {film_id} was deleted successfully",
        "film_id": str(film_id),
        "status": "success",
    }
