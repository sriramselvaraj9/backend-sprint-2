from app.schemas.film import FilmCreate, FilmYearRange


async def get_all_films() -> dict:
    return {
        "message": "Films fetched successfully",
        "films": [
            {
                "id": 1,
                "title": "Inception",
                "director": "Christopher Nolan",
                "release_year": 2010,
                "genre": "Sci-Fi"
            },
            {
                "id": 2,
                "title": "Interstellar",
                "director": "Christopher Nolan",
                "release_year": 2014,
                "genre": "Sci-Fi"
            }
        ]
    }


async def get_film_by_id(film_id: int) -> dict:
    return {
        "message": f"Film with ID {film_id} fetched successfully",
        "film": {
            "id": film_id,
            "title": "Inception",
            "director": "Christopher Nolan",
            "release_year": 2010,
            "genre": "Sci-Fi"
        }
    }


async def create_film(film_data: FilmCreate) -> dict:
    return {
        "id": 1,
        "title": film_data.title,
        "director": film_data.director,
        "release_year": film_data.release_year,
        "genre": film_data.genre
    }


async def filter_films_by_year_range(year_range: FilmYearRange) -> dict:
    return {
        "message": f"Successfully filtered films between {year_range.start_year} and {year_range.end_year}",
        "start_year": year_range.start_year,
        "end_year": year_range.end_year,
        "matching_films": [
            {"id": 1, "title": "Inception", "release_year": 2010}
        ]
    }


async def update_film(film_id: int) -> dict:
    return {
        "message": f"Film with ID {film_id} updated successfully",
        "film_id": film_id,
        "status": "success"
    }


async def delete_film(film_id: int) -> dict:
    return {
        "message": f"Film with ID {film_id} was deleted successfully",
        "film_id": film_id,
        "status": "success"
    }
