import uuid
from datetime import UTC, datetime

from pydantic import Field, computed_field, field_validator, model_validator

from app.schemas.common import BaseSchema


class FilmBase(BaseSchema):
    """
    Base schema for film containing common attributes and validation.
    """

    title: str = Field(..., min_length=1, max_length=255, description="Title of the film")
    release_year: int = Field(..., ge=1888, description="Year the film was released (1888 or later)")
    genre: str = Field(..., min_length=1, max_length=100, description="Genre of the film")
    director: str = Field(..., min_length=1, max_length=255, description="Director of the film")

    @field_validator("release_year")
    @classmethod
    def validate_release_year_not_future(cls, value: int) -> int:
        current_year = datetime.now(UTC).year
        if value > current_year + 5:
            raise ValueError(f"release_year cannot be more than 5 years in the future (max {current_year + 5})")
        return value


class FilmResponse(FilmBase):
    """
    Schema for film responses.
    Inherits core film attributes from FilmBase, adds id and computed years_ago.
    """

    id: uuid.UUID = Field(..., description="Unique identifier of the film")

    @field_validator("id", mode="before")
    @classmethod
    def parse_id(cls, value: object) -> uuid.UUID | object:
        if isinstance(value, str):
            try:
                return uuid.UUID(value)
            except ValueError:
                return value
        return value

    @computed_field  # type: ignore[prop-decorator]
    @property
    def years_ago(self) -> int:
        """
        Computed field calculating how many years ago the film was released.
        Calculated automatically from release_year; client does not send this.
        """
        current_year = datetime.now(UTC).year
        return max(0, current_year - self.release_year)


class FilmYearRange(BaseSchema):
    start_year: int = Field(..., description="Start release year")
    end_year: int = Field(..., description="End release year")

    @model_validator(mode="after")
    def validate_year_order(self) -> "FilmYearRange":
        if self.start_year >= self.end_year:
            raise ValueError("start_year must be strictly less than end_year (start_year < end_year)")
        return self


class FilmCreate(FilmBase):
    """
    Schema for creating a new film.
    Inherits all core attributes and validation from FilmBase.
    """
