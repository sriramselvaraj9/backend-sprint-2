from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    """
    Reusable Pydantic v2 base schema for all Day 2 models.
    
    Configuration:
    - strict=True: Prevents type coercion (e.g., "2020" will NOT coerce to int 2020)
    - str_strip_whitespace=True: Automatically strips leading and trailing whitespace from strings
    """
    model_config = ConfigDict(
        strict=True,
        str_strip_whitespace=True
    )
    
