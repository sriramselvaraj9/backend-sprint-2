from datetime import datetime, timezone
from app.schemas.review import ReviewCreate


async def get_film_reviews(film_id: int) -> dict:
    return {
        "message": f"Reviews for film ID {film_id} fetched successfully",
        "film_id": film_id,
        "reviews": [
            {
                "id": 1,
                "film_id": film_id,
                "rating": 9,
                "body": "This is an extraordinary visual and philosophical cinematic journey that deserves praise.",
                "reviewer_display_name": "CinemaExpert",
                "submitted_at": datetime.now(timezone.utc)
            },
            {
                "id": 2,
                "film_id": film_id,
                "rating": 8,
                "body": "A thrilling and intricately layered masterpiece that keeps you engaged throughout.",
                "reviewer_display_name": "SciFiFanatic",
                "submitted_at": datetime.now(timezone.utc)
            }
        ]
    }


async def create_film_review(film_id: int, review_data: ReviewCreate) -> dict:
    return {
        "id": 1,
        "film_id": film_id,
        "rating": review_data.rating,
        "body": review_data.body,
        "reviewer_display_name": "FilmCritic99",
        "submitted_at": datetime.now(timezone.utc)
    }


async def create_review(review_data: ReviewCreate) -> dict:
    return {
        "id": 1,
        "film_id": review_data.film_id,
        "rating": review_data.rating,
        "body": review_data.body,
        "reviewer_display_name": "FilmCritic99",
        "submitted_at": datetime.now(timezone.utc)
    }


async def update_review(review_id: int) -> dict:
    return {
        "message": f"Review with ID {review_id} updated successfully",
        "review_id": review_id,
        "status": "success"
    }


async def delete_review(review_id: int) -> dict:
    return {
        "message": f"Review with ID {review_id} was deleted successfully",
        "review_id": review_id,
        "status": "success"
    }
