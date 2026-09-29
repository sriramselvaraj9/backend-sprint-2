from datetime import datetime
from pydantic import Field
from app.schemas.common import BaseSchema


class ReviewBase(BaseSchema):
    """
    Base schema for review containing common fields.
    - film_id: strict integer
    - rating: strict integer between 1 and 10
    - body: at least 50 characters
    """
    film_id: int = Field(..., description="ID of the film being reviewed")
    rating: int = Field(..., ge=1, le=10, description="Rating between 1 and 10")
    body: str = Field(..., min_length=50, description="Detailed review body (minimum 50 characters)")


class ReviewCreate(ReviewBase):
    """
    Schema for creating a review.
    Inherits all core review fields and constraints from ReviewBase.
    """
    pass


class ReviewResponse(ReviewBase):
    """
    Response schema for reviews.
    Inherits core review fields from ReviewBase, adds id, reviewer_display_name, and submitted_at.
    """
    id: int = Field(..., description="Unique review identifier")
    reviewer_display_name: str = Field(..., description="Public display name of reviewer")
    submitted_at: datetime = Field(..., description="Timestamp when review was submitted")
