from pydantic import Field
from app.schemas.common import BaseSchema


class UserBase(BaseSchema):
    """
    Base schema for user containing shared profile attributes.
    """
    username: str = Field(..., min_length=3, max_length=50, description="Username for the account")
    email: str = Field(..., min_length=5, max_length=120, description="User email address")


class UserCreate(UserBase):
    """
    Schema for user registration.
    Inherits username and email from UserBase, adds password.
    """
    password: str = Field(..., min_length=8, description="User password (minimum 8 characters)")


class UserResponse(UserBase):
    """
    User response schema.
    Inherits username and email from UserBase, adds role.
    MUST NOT contain password.
    """
    role: str = Field(default="user", description="User role in the system")


class LoginRequest(BaseSchema):
    """
    Schema for user login credentials.
    """
    email: str = Field(..., description="User email address")
    password: str = Field(..., description="User password")
