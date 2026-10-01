from pydantic import BaseModel, ConfigDict


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
