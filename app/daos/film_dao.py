import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.film import Film
from app.schemas.film import FilmCreate, FilmResponse, FilmYearRange


class FilmDAO:
    """
    Typed async Data Access Object for the Film entity.
    Encapsulates all direct database queries and mutations for films.
    Receives an AsyncSession through dependency injection.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, film_id: uuid.UUID | str, active_only: bool = True) -> Film | None:
        """
        Accept film_id: uuid.UUID or str.
        Return Film | None.
        When active_only is True (default), soft-deleted films (is_active == False) are excluded.
        Uses select() and scalar_one_or_none().
        """
        if isinstance(film_id, str):
            try:
                film_id = uuid.UUID(film_id)
            except ValueError:
                return None

        stmt = select(Film).where(Film.id == film_id)
        if active_only:
            stmt = stmt.where(Film.is_active == True)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_films(
        self,
        genre: str | None = None,
        min_year: int | None = None,
        max_year: int | None = None,
    ) -> list[Film]:
        """
        Return all active films.
        Supports optional filtering:
        - genre
        - minimum release year
        - maximum release year
        Filters are applied only when provided.
        Uses result.scalars().all().
        """
        stmt = select(Film).where(Film.is_active == True)

        if genre is not None and genre.strip():
            stmt = stmt.where(Film.genre.ilike(f"%{genre.strip()}%"))

        if min_year is not None:
            stmt = stmt.where(Film.release_year >= min_year)

        if max_year is not None:
            stmt = stmt.where(Film.release_year <= max_year)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, film: Film) -> Film:
        """
        Accept a Film ORM object.
        Add it to the session, commit, refresh, and return it.
        """
        self.session.add(film)
        await self.session.commit()
        await self.session.refresh(film)
        return film

    async def update(
        self,
        film: Film,
        update_data: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Film | None:
        """
        Update only the fields provided for an existing active film ORM object.
        If film is soft-deleted (is_active == False), returns None.
        Commit and refresh the object, return Film.
        """
        if not film.is_active:
            return None

        fields: dict[str, Any] = {}
        if update_data:
            fields.update(update_data)
        fields.update(kwargs)

        for key, value in fields.items():
            if value is not None and hasattr(film, key):
                setattr(film, key, value)

        await self.session.commit()
        await self.session.refresh(film)
        return film

    async def soft_delete(self, film_or_id: Film | uuid.UUID | str) -> Film | None:
        """
        Soft delete a film by setting is_active to False.
        Does NOT physically delete the row.
        Returns the updated Film or None if film does not exist or was already soft-deleted.
        """
        if isinstance(film_or_id, (uuid.UUID, str)):
            target_id = uuid.UUID(str(film_or_id)) if isinstance(film_or_id, str) else film_or_id
            film = await self.get_by_id(target_id, active_only=True)
            if film is None:
                return None
        else:
            film = film_or_id
            if not film.is_active:
                return None

        film.is_active = False
        await self.session.commit()
        await self.session.refresh(film)
        return film

    @staticmethod
    async def soft_delete_film(db: AsyncSession, film_id: uuid.UUID | str) -> bool:
        """
        Soft delete a film by setting is_active to False.
        Returns True if film was found and soft-deleted, False otherwise.
        """
        dao = FilmDAO(db)
        film = await dao.soft_delete(film_id)
        return film is not None

    # Alias for update_film
    update_film = update


# ---------------------------------------------------------
# Standalone functions for backward compatibility
# ---------------------------------------------------------
async def get_all_films(
    db: AsyncSession,
    genre: str | None = None,
) -> dict:
    dao = FilmDAO(db)
    films = await dao.list_films(genre=genre)
    films_data = [FilmResponse.model_validate(f).model_dump() for f in films]
    return {
        "message": "Films fetched successfully",
        "films": films_data,
    }


async def get_film_by_id(
    film_id: uuid.UUID | str,
    db: AsyncSession,
) -> dict:
    dao = FilmDAO(db)
    film = await dao.get_by_id(film_id, active_only=True)
    if film:
        return {
            "message": f"Film with ID {film_id} fetched successfully",
            "film": FilmResponse.model_validate(film).model_dump(),
        }
    return {
        "message": f"Film with ID {film_id} not found",
        "film": None,
    }


async def create_film(
    film_data: FilmCreate,
    db: AsyncSession,
) -> dict:
    dao = FilmDAO(db)
    new_film = Film(
        title=film_data.title,
        release_year=film_data.release_year,
        genre=film_data.genre,
        director=film_data.director,
    )
    created = await dao.create(new_film)
    return FilmResponse.model_validate(created).model_dump()


async def filter_films_by_year_range(
    year_range: FilmYearRange,
    db: AsyncSession,
) -> dict:
    dao = FilmDAO(db)
    films = await dao.list_films(
        min_year=year_range.start_year,
        max_year=year_range.end_year,
    )
    matching = [FilmResponse.model_validate(f).model_dump() for f in films]
    return {
        "message": f"Successfully filtered films between {year_range.start_year} and {year_range.end_year}",
        "start_year": year_range.start_year,
        "end_year": year_range.end_year,
        "matching_films": matching,
    }


async def update_film(
    film_id: uuid.UUID | str,
    db: AsyncSession,
    update_data: dict[str, Any] | None = None,
    **kwargs: Any,
) -> dict:
    dao = FilmDAO(db)
    film = await dao.get_by_id(film_id, active_only=True)
    if film:
        await dao.update(film, update_data=update_data, **kwargs)
        return {
            "message": f"Film with ID {film_id} updated successfully",
            "film_id": str(film_id),
            "status": "success",
            "film": FilmResponse.model_validate(film).model_dump(),
        }
    return {
        "message": f"Film with ID {film_id} not found",
        "film_id": str(film_id),
        "status": "error",
    }


async def delete_film(
    film_id: uuid.UUID | str,
    db: AsyncSession,
) -> dict:
    dao = FilmDAO(db)
    film = await dao.soft_delete(film_id)
    if film:
        return {
            "message": f"Film with ID {film_id} was deleted successfully",
            "film_id": str(film_id),
            "status": "success",
        }
    return {
        "message": f"Film with ID {film_id} not found",
        "film_id": str(film_id),
        "status": "error",
    }


async def soft_delete_film(
    film_id: uuid.UUID | str,
    db: AsyncSession,
) -> bool:
    return await FilmDAO.soft_delete_film(db, film_id)
