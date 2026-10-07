import uuid
from datetime import datetime

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


# Alias for RegisterRequest
RegisterRequest = UserCreate


class UserResponse(UserBase):
    """
    User response schema.
    Inherits username and email from UserBase, adds id and role.
    MUST NOT contain password or password_hash.
    """

    id: uuid.UUID = Field(..., description="Unique user identifier")
    role: str = Field(default="user", description="User role in the system")
    created_at: datetime | None = Field(default=None, description="Account creation timestamp")


class LoginRequest(BaseSchema):
    """
    Schema for user login credentials.
    """

    email: str = Field(..., description="User email address")
    password: str = Field(..., description="User password")


class TokenResponse(BaseSchema):
    """
    Schema for authentication tokens response.
    """

    access_token: str = Field(..., description="Short-lived JWT access token")
    refresh_token: str | None = Field(default=None, description="Long-lived JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type (Bearer)")


class RefreshRequest(BaseSchema):
    """
    Schema for refreshing access tokens using a refresh token.
    """

    refresh_token: str = Field(..., description="Refresh token string")


class AuthenticatedUser(BaseSchema):
    """
    Schema representing the authenticated user decoded from JWT claims.
    """

    id: uuid.UUID = Field(..., description="Authenticated user ID")
    role: str = Field(default="user", description="Authenticated user role")
    username: str | None = Field(default=None, description="Authenticated username")
    email: str | None = Field(default=None, description="Authenticated user email")
