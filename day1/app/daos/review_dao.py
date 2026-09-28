from app.schemas.review import ReviewCreate


async def get_film_reviews(film_id: int) -> dict:
    return {
        "message": f"Reviews for film ID {film_id} fetched successfully",
        "film_id": film_id,
        "reviews": [
            {
                "id": 1,
                "film_id": film_id,
                "rating": 5,
                "comment": "Masterpiece! Amazing visuals and storyline."
            },
            {
                "id": 2,
                "film_id": film_id,
                "rating": 4,
                "comment": "Great cinematography and soundtrack."
            }
        ]
    }


async def create_film_review(film_id: int, review_data: ReviewCreate) -> dict:
    return {
        "id": 1,
        "film_id": film_id,
        "rating": review_data.rating,
        "comment": review_data.comment
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

