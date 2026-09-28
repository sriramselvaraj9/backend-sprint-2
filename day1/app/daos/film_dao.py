from app.schemas.film import FilmCreate


async def get_all_films() -> dict:
    return {
        "message": "Films fetched successfully",
        "films": [
            {"id": 1, "title": "Inception", "director": "Christopher Nolan", "release_year": 2010},
            {"id": 2, "title": "Interstellar", "director": "Christopher Nolan", "release_year": 2014}
        ]
    }


async def get_film_by_id(film_id: int) -> dict:
    return {
        "message": f"Film with ID {film_id} fetched successfully",
        "film": {
            "id": film_id,
            "title": "Inception",
            "director": "Christopher Nolan",
            "release_year": 2010
        }
    }


async def create_film(film_data: FilmCreate) -> dict:
    return {
        "id": 1,
        "title": film_data.title,
        "director": film_data.director,
        "release_year": film_data.release_year
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

