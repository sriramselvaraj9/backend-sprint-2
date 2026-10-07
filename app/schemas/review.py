import uuid
from datetime import datetime

from pydantic import Field

from app.schemas.common import BaseSchema


class ReviewBase(BaseSchema):
    """
    Base schema for review containing common fields.
    - film_id: UUID
    - rating: strict integer between 1 and 10
    - body: at least 50 characters
    """

    film_id: uuid.UUID = Field(..., description="ID of the film being reviewed", strict=False)
    rating: int = Field(..., ge=1, le=10, description="Rating between 1 and 10")
    body: str = Field(..., min_length=50, description="Detailed review body (minimum 50 characters)")


class ReviewCreate(ReviewBase):
    """
    Schema for creating a review.
    Inherits all core review fields and constraints from ReviewBase.
    Optionally accepts a user_id.
    """

    user_id: uuid.UUID | None = Field(None, description="Optional user ID of the reviewer", strict=False)


class ReviewUpdate(BaseSchema):
    """
    Schema for updating an existing review.
    Only rating and body can be modified.
    """

    rating: int | None = Field(None, ge=1, le=10, description="Updated rating between 1 and 10")
    body: str | None = Field(None, min_length=50, description="Updated review body (minimum 50 characters)")
    user_id: uuid.UUID | None = Field(None, description="ID of user requesting the update", strict=False)


class ReviewResponse(ReviewBase):
    """
    Response schema for reviews.
    Inherits core review fields from ReviewBase, adds id, reviewer_display_name, and submitted_at.
    """

    id: uuid.UUID = Field(..., description="Unique review identifier", strict=False)
    reviewer_display_name: str = Field(..., description="Public display name of reviewer")
    submitted_at: datetime = Field(..., description="Timestamp when review was submitted")
