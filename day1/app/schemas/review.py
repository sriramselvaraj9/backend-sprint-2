from pydantic import BaseModel


class ReviewCreate(BaseModel):
    rating: int
    comment: str


class ReviewResponse(BaseModel):
    id: int
    film_id: int
    rating: int
    comment: str
