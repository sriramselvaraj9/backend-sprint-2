import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.daos.film_dao import FilmDAO
from app.daos.review_dao import ReviewDAO
from app.schemas.film import FilmCreate, FilmResponse, FilmYearRange
from app.services.film_service import FilmService


class FilmHandler:
    """
    Handler layer for Film requests.
    Translates HTTP layer requests to Service operations and formats responses.
    Contains NO direct database queries or business logic.
    """

    def __init__(self, service: FilmService) -> None:
        self.service = service

    async def get_all_films(self, genre: str | None = None) -> dict:
        films = await self.service.list_films(genre=genre)
        films_data = [FilmResponse.model_validate(f).model_dump() for f in films]
        return {
            "message": "Films fetched successfully",
            "films": films_data,
        }

    async def get_film_by_id(self, film_id: uuid.UUID | str) -> dict:
        film = await self.service.get_film_by_id(film_id)
        return {
            "message": f"Film with ID {film_id} fetched successfully",
            "film": FilmResponse.model_validate(film).model_dump(),
        }

    async def create_film(self, film_data: FilmCreate) -> dict:
        film = await self.service.create_film(film_data)
        return FilmResponse.model_validate(film).model_dump()

    async def filter_films_by_year_range(self, year_range: FilmYearRange) -> dict:
        films = await self.service.filter_films_by_year_range(year_range)
        matching = [FilmResponse.model_validate(f).model_dump() for f in films]
        return {
            "message": f"Successfully filtered films between {year_range.start_year} and {year_range.end_year}",
            "start_year": year_range.start_year,
            "end_year": year_range.end_year,
            "matching_films": matching,
        }

    async def update_film(
        self,
        film_id: uuid.UUID | str,
        update_data: dict[str, Any] | None = None,
    ) -> dict:
        film = await self.service.update_film(film_id, update_data=update_data)
        return {
            "message": f"Film with ID {film_id} updated successfully",
            "film_id": str(film_id),
            "status": "success",
            "film": FilmResponse.model_validate(film).model_dump(),
        }

    async def delete_film(self, film_id: uuid.UUID | str) -> dict:
        await self.service.delete_film(film_id)
        return {
            "message": f"Film with ID {film_id} was deleted successfully",
            "film_id": str(film_id),
            "status": "success",
        }


# ---------------------------------------------------------
# Standalone functions for backward compatibility
# ---------------------------------------------------------
async def handle_get_all_films(
    db: AsyncSession,
    genre: str | None = None,
) -> dict:
    service = FilmService(FilmDAO(db), ReviewDAO(db))
    handler = FilmHandler(service)
    return await handler.get_all_films(genre=genre)


async def handle_get_film_by_id(
    film_id: uuid.UUID,
    db: AsyncSession,
) -> dict:
    service = FilmService(FilmDAO(db), ReviewDAO(db))
    handler = FilmHandler(service)
    return await handler.get_film_by_id(film_id)


async def handle_create_film(
    film_data: FilmCreate,
    db: AsyncSession,
) -> dict:
    service = FilmService(FilmDAO(db), ReviewDAO(db))
    handler = FilmHandler(service)
    return await handler.create_film(film_data)


async def handle_filter_films_by_year_range(
    year_range: FilmYearRange,
    db: AsyncSession,
) -> dict:
    service = FilmService(FilmDAO(db), ReviewDAO(db))
    handler = FilmHandler(service)
    return await handler.filter_films_by_year_range(year_range)


async def handle_update_film(
    film_id: uuid.UUID,
    db: AsyncSession,
) -> dict:
    service = FilmService(FilmDAO(db), ReviewDAO(db))
    handler = FilmHandler(service)
    return await handler.update_film(film_id)


async def handle_delete_film(
    film_id: uuid.UUID,
    db: AsyncSession,
) -> dict:
    service = FilmService(FilmDAO(db), ReviewDAO(db))
    handler = FilmHandler(service)
    return await handler.delete_film(film_id)
