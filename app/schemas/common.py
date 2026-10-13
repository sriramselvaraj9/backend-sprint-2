from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class BaseSchema(BaseModel):
    """
    Reusable Pydantic v2 base schema for all models.

    Configuration:
    - strict=True: Prevents type coercion (e.g., "2020" will NOT coerce to int 2020)
    - str_strip_whitespace=True: Automatically strips leading and trailing whitespace from strings
    - from_attributes=True: Enables reading attributes directly from ORM models (SQLAlchemy)
    """

    model_config = ConfigDict(
        strict=True,
        str_strip_whitespace=True,
        from_attributes=True,
    )


class PaginationParams(BaseModel):
    """
    Query schema for offset-based pagination.
    Validates page >= 1 and 1 <= page_size <= 100 with sensible defaults.
    """

    page: int = Field(default=1, ge=1, description="Page number (>= 1)")
    page_size: int = Field(default=10, ge=1, le=100, description="Page size (1-100)")

    model_config = ConfigDict(
        str_strip_whitespace=True,
        from_attributes=True,
    )


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Generic envelope for offset-paginated responses.
    """

    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of items requested per page")
    total: int = Field(..., description="Total matching items across all pages")
    items: list[T] = Field(..., description="Records for the requested page")

    model_config = ConfigDict(
        str_strip_whitespace=True,
        from_attributes=True,
    )

