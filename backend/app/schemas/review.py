import uuid
from datetime import datetime

from pydantic import Field, field_validator

from app.schemas.common import BaseSchema


class ReviewBase(BaseSchema):
    """
    Base schema for review containing common fields.
    - film_id: UUID
    - rating: strict integer between 1 and 10
    - body: between 10 and 250 characters
    """

    film_id: uuid.UUID = Field(..., description="ID of the film being reviewed", strict=False)
    rating: int = Field(..., ge=1, le=10, description="Rating between 1 and 10")
    body: str = Field(..., min_length=10, max_length=250, description="Detailed review body (minimum 10 characters, maximum 250 characters)")

    @field_validator("body")
    @classmethod
    def validate_body_length(cls, v: str) -> str:
        trimmed = v.strip()
        if len(trimmed) < 10:
            raise ValueError(f"Review body must contain at least 10 characters (currently {len(trimmed)})")
        if len(trimmed) > 250:
            raise ValueError(f"Review body cannot exceed 250 characters (currently {len(trimmed)})")
        return v
 

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
    body: str | None = Field(None, min_length=10, max_length=250, description="Updated review body (maximum 250 characters)")
    user_id: uuid.UUID | None = Field(None, description="ID of user requesting the update", strict=False)

    @field_validator("body")
    @classmethod
    def validate_body_length(cls, v: str | None) -> str | None:
        if v is not None:
            trimmed = v.strip()
            if len(trimmed) < 10:
                raise ValueError(f"Review body must contain at least 10 characters (currently {len(trimmed)})")
            if len(trimmed) > 250:
                raise ValueError(f"Review body cannot exceed 250 characters (currently {len(trimmed)})")
        return v


class ReviewResponse(ReviewBase):
    """
    Response schema for reviews.
    Inherits core review fields from ReviewBase, adds id, reviewer_display_name, and submitted_at.
    """

    id: uuid.UUID = Field(..., description="Unique review identifier", strict=False)
    reviewer_display_name: str = Field(..., description="Public display name of reviewer")
    submitted_at: datetime = Field(..., description="Timestamp when review was submitted")
