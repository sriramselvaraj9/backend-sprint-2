from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.film import Film
from app.schemas.film import FilmCreate, FilmResponse, FilmYearRange


async def get_all_films(
    db: AsyncSession,
    genre: str | None = None
) -> dict:
    """
    7. Real Database Read
    Retrieve all films from PostgreSQL using SQLAlchemy 2.0 async select.
    Applies optional genre filter.
    Returns data validated against the Day 2 FilmResponse schema.
    """
    stmt = select(Film) #Build the SQL statement

    if genre and genre.strip():
        stmt = stmt.where(Film.genre.ilike(f"%{genre.strip()}%"))

    result = await db.execute(stmt)
    films = result.scalars().all()

    films_data = [FilmResponse.model_validate(f).model_dump() for f in films]

    return {
        "message": "Films fetched successfully",
        "films": films_data
    }


async def get_film_by_id(
    film_id: int,
    db: AsyncSession
) -> dict:
    """
    Retrieve a single film by ID from PostgreSQL.
    """
    stmt = select(Film).where(Film.id == film_id)
    result = await db.execute(stmt)
    film = result.scalar_one_or_none()

    if film:
        film_response = FilmResponse.model_validate(film).model_dump()
        return {
            "message": f"Film with ID {film_id} fetched successfully",
            "film": film_response
        }
    return {
        "message": f"Film with ID {film_id} not found",
        "film": None
    }


async def create_film(
    film_data: FilmCreate,
    db: AsyncSession
) -> dict:
    """
    Create a new film record in PostgreSQL.
    """
    new_film = Film(
        title=film_data.title,
        release_year=film_data.release_year,
        genre=film_data.genre,
        director=film_data.director,
    )
    db.add(new_film)
    await db.commit()
    await db.refresh(new_film)

    return FilmResponse.model_validate(new_film).model_dump()


async def filter_films_by_year_range(
    year_range: FilmYearRange,
    db: AsyncSession
) -> dict:
    """
    Filter films by release year range directly in PostgreSQL.
    """
    stmt = (
        select(Film)
        .where(Film.release_year >= year_range.start_year)
        .where(Film.release_year <= year_range.end_year)
    )
    result = await db.execute(stmt)
    films = result.scalars().all()
    matching = [FilmResponse.model_validate(f).model_dump() for f in films]

    return {
        "message": f"Successfully filtered films between {year_range.start_year} and {year_range.end_year}",
        "start_year": year_range.start_year,
        "end_year": year_range.end_year,
        "matching_films": matching
    }


async def update_film(
    film_id: int,
    db: AsyncSession
) -> dict:
    return {
        "message": f"Film with ID {film_id} updated successfully",
        "film_id": film_id,
        "status": "success"
    }


async def delete_film(
    film_id: int,
    db: AsyncSession
) -> dict:
    stmt = select(Film).where(Film.id == film_id)
    result = await db.execute(stmt)
    film = result.scalar_one_or_none()
    if film:
        await db.delete(film)
        await db.commit()
        return {
            "message": f"Film with ID {film_id} was deleted successfully",
            "film_id": film_id,
            "status": "success"
        }

    return {
        "message": f"Film with ID {film_id} not found",
        "film_id": film_id,
        "status": "error"
    }
