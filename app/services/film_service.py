import logging
import uuid
from typing import Any

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.film_cache import FilmCache
from app.daos.film_dao import FilmDAO
from app.daos.review_dao import ReviewDAO
from app.exceptions.domain import (
    FilmHasActiveReviewsError,
    FilmNotFoundError,
)
from app.models.film import Film
from app.schemas.film import FilmCreate, FilmResponse, FilmYearRange

logger = logging.getLogger("film_service")


class FilmService:
    """
    Service layer for Film business operations.
    Coordinates FilmDAO, ReviewDAO, and FilmCache to enforce business rules and fast reads.
    Contains NO direct SQLAlchemy queries or session executions, and NO low-level Redis calls.
    """

    def __init__(
        self,
        film_dao: FilmDAO,
        review_dao: ReviewDAO | None = None,
        cache: FilmCache | None = None,
        redis_client: redis.Redis | None = None,
    ) -> None:
        self.film_dao = film_dao
        self.review_dao = review_dao if review_dao is not None else ReviewDAO(film_dao.session)
        if cache is not None:
            self.cache = cache
        elif redis_client is not None:
            self.cache = FilmCache(redis_client)
        else:
            self.cache = FilmCache(None)
        # Compatibility aliases
        self.dao = self.film_dao
        self.redis_client = getattr(self.cache, "redis_client", None)

    def _build_cache_key(
        self,
        genre: str | None = None,
        min_year: int | None = None,
        max_year: int | None = None,
    ) -> str:
        """Compatibility helper delegating key generation to FilmCache."""
        return self.cache.build_key(genre=genre, min_year=min_year, max_year=max_year)

    async def _invalidate_film_cache(self) -> None:
        """Compatibility helper delegating cache invalidation to FilmCache."""
        await self.cache.invalidate()

    async def get_film_by_id(self, film_id: uuid.UUID | str) -> Film:
        """
        Retrieve a single active film by ID through FilmDAO.
        Raises FilmNotFoundError if the film is missing or soft-deleted.
        """
        logger.info(f"Fetching film with ID {film_id}")
        film = await self.film_dao.get_by_id(film_id, active_only=True)
        if film is None:
            logger.warning(f"Film with ID {film_id} not found")
            raise FilmNotFoundError(film_id=film_id)
        return film

    async def list_films(
        self,
        genre: str | None = None,
        min_year: int | None = None,
        max_year: int | None = None,
    ) -> list[Any]:
        
        cache_key = self.cache.build_key(genre=genre, min_year=min_year, max_year=max_year)
        logger.info(f"Listing films with filters: genre={genre}, min_year={min_year}, max_year={max_year}")

        # 1. Check FilmCache
        cached = await self.cache.get(cache_key)
        if cached is not None:
            return cached
 
        # 2. Cache MISS: Query PostgreSQL through FilmDAO
        logger.info(f"Cache MISS for key: '{cache_key}'. Querying PostgreSQL via FilmDAO.")
        films = await self.film_dao.list_films(
            genre=genre,
            min_year=min_year,
            max_year=max_year,
        )

        # 3. Store in Redis via FilmCache with TTL
        await self.cache.set(cache_key, films)

        return films

    async def create_film(self, film_data: FilmCreate) -> Film:
        """
        Build a Film ORM instance, persist it through FilmDAO,
        and invalidate film list cache.
        """
        logger.info(f"Creating film '{film_data.title}'")
        new_film = Film(
            title=film_data.title,
            release_year=film_data.release_year,
            genre=film_data.genre,
            director=film_data.director,
        )
        created_film = await self.film_dao.create(new_film)
        logger.info(f"Film created successfully with ID {created_film.id}")

        # Invalidate film list cache after creation
        await self.cache.invalidate()
        return created_film

    async def filter_films_by_year_range(self, year_range: FilmYearRange) -> list[Any]:
        """
        Filter films by start and end release years through list_films (cached).
        """
        logger.info(f"Filtering films between {year_range.start_year} and {year_range.end_year}")
        return await self.list_films(
            min_year=year_range.start_year,
            max_year=year_range.end_year,
        )

    async def update_film(
        self,
        film_id: uuid.UUID | str,
        update_data: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Film:
        """
        Find active film by ID, update fields through FilmDAO,
        and invalidate film list cache.
        Raises FilmNotFoundError if film does not exist.
        """
        logger.info(f"Updating film with ID {film_id}")
        film = await self.film_dao.get_by_id(film_id, active_only=True)
        if film is None:
            logger.warning(f"Film update failed: Film {film_id} not found")
            raise FilmNotFoundError(film_id=film_id)

        updated_film = await self.film_dao.update(film, update_data=update_data, **kwargs)
        if updated_film is None:
            logger.warning(f"Film update failed: Film {film_id} could not be updated")
            raise FilmNotFoundError(film_id=film_id)
        logger.info(f"Film with ID {film_id} updated successfully")

        # Invalidate film list cache after update
        await self.cache.invalidate()
        return updated_film

    async def delete_film(self, film_id: uuid.UUID | str) -> Film:
        """
        Soft-delete film by ID enforcing the film soft-delete rule:
        A film cannot be soft-deleted if it still has active reviews.
        Invalidates film list cache upon successful deletion.
        """
        logger.info(f"Initiating soft-delete for film {film_id}")

        # 1. Verify that the film exists and is active
        film = await self.film_dao.get_by_id(film_id, active_only=True)
        if film is None:
            logger.warning(f"Film deletion failed: Film {film_id} not found")
            raise FilmNotFoundError(film_id=film_id)

        # 2. Check active reviews through ReviewDAO
        logger.info(f"Checking active reviews for film {film_id}")
        active_reviews = await self.review_dao.list_by_film(film.id)

        if len(active_reviews) > 0:
            logger.warning(f"Film deletion rejected because active reviews exist for film {film_id}")
            raise FilmHasActiveReviewsError(
                film_id=film_id,
                active_review_count=len(active_reviews),
            )

        # 3. If no active reviews exist, request FilmDAO to soft-delete the film
        deleted_film = await self.film_dao.soft_delete(film)
        if deleted_film is None:
            logger.warning(f"Film deletion failed: Film {film_id} could not be deleted")
            raise FilmNotFoundError(film_id=film_id)
        logger.info(f"Film soft-deleted successfully: {film_id}")

        # Invalidate film list cache after soft-delete
        await self.cache.invalidate()
        return deleted_film


# ---------------------------------------------------------
# Standalone functions for backward compatibility
# ---------------------------------------------------------
async def get_all_films(
    db: AsyncSession,
    genre: str | None = None,
) -> dict:
    from app.core.redis import redis_client

    service = FilmService(FilmDAO(db), ReviewDAO(db), cache=FilmCache(redis_client))
    films = await service.list_films(genre=genre)
    films_data = [FilmResponse.model_validate(f).model_dump() for f in films]
    return {
        "message": "Films fetched successfully",
        "films": films_data,
    }


async def get_film_by_id(
    film_id: uuid.UUID,
    db: AsyncSession,
) -> dict:
    from app.core.redis import redis_client

    service = FilmService(FilmDAO(db), ReviewDAO(db), cache=FilmCache(redis_client))
    try:
        film = await service.get_film_by_id(film_id)
        return {
            "message": f"Film with ID {film_id} fetched successfully",
            "film": FilmResponse.model_validate(film).model_dump(),
        }
    except FilmNotFoundError:
        return {
            "message": f"Film with ID {film_id} not found",
            "film": None,
        }


async def create_film(
    film_data: FilmCreate,
    db: AsyncSession,
) -> dict:
    from app.core.redis import redis_client

    service = FilmService(FilmDAO(db), ReviewDAO(db), cache=FilmCache(redis_client))
    created = await service.create_film(film_data)
    return FilmResponse.model_validate(created).model_dump()


async def filter_films_by_year_range(
    year_range: FilmYearRange,
    db: AsyncSession,
) -> dict:
    from app.core.redis import redis_client

    service = FilmService(FilmDAO(db), ReviewDAO(db), cache=FilmCache(redis_client))
    films = await service.filter_films_by_year_range(year_range)
    matching = [FilmResponse.model_validate(f).model_dump() for f in films]
    return {
        "message": f"Successfully filtered films between {year_range.start_year} and {year_range.end_year}",
        "start_year": year_range.start_year,
        "end_year": year_range.end_year,
        "matching_films": matching,
    }


async def update_film(
    film_id: uuid.UUID,
    db: AsyncSession,
) -> dict:
    from app.core.redis import redis_client

    service = FilmService(FilmDAO(db), ReviewDAO(db), cache=FilmCache(redis_client))
    try:
        await service.update_film(film_id)
        return {
            "message": f"Film with ID {film_id} updated successfully",
            "film_id": film_id,
            "status": "success",
        }
    except FilmNotFoundError:
        return {
            "message": f"Film with ID {film_id} not found",
            "film_id": film_id,
            "status": "error",
        }


async def delete_film(
    film_id: uuid.UUID,
    db: AsyncSession,
) -> dict:
    from app.core.redis import redis_client

    service = FilmService(FilmDAO(db), ReviewDAO(db), cache=FilmCache(redis_client))
    try:
        await service.delete_film(film_id)
        return {
            "message": f"Film with ID {film_id} was deleted successfully",
            "film_id": film_id,
            "status": "success",
        }
    except Exception:  # noqa: BLE001
        return {
            "message": f"Film with ID {film_id} not found",
            "film_id": film_id,
            "status": "error",
        }
