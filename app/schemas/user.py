import uuid
from datetime import datetime
from enum import Enum

from pydantic import Field, field_validator

from app.schemas.common import BaseSchema


class UserRole(str, Enum):
    ADMIN = "admin"
    CRITIC = "critic"
    VIEWER = "viewer"


class RegisterRole(str, Enum):
    VIEWER = "viewer"
    CRITIC = "critic"


class UserBase(BaseSchema):
    """
    Base schema for user containing shared profile attributes.
    """

    username: str = Field(..., min_length=3, max_length=50, description="Username for the account")
    email: str = Field(..., min_length=5, max_length=120, description="User email address")


class UserCreate(UserBase):
    """
    Schema for user registration.
    Inherits username and email from UserBase, adds password and role ('viewer' or 'critic').
    Admin accounts cannot be created via public registration.
    """

    password: str = Field(..., min_length=8, description="User password (minimum 8 characters)")
    role: RegisterRole = Field(default=RegisterRole.VIEWER, description="User role ('viewer' or 'critic')")

    @field_validator("role", mode="before")
    @classmethod
    def validate_role(cls, v: object) -> RegisterRole:
        if v is None:
            return RegisterRole.VIEWER
        if isinstance(v, RegisterRole):
            return v
        role_str = str(v).lower()
        if role_str == "admin":
            raise ValueError("Admin accounts cannot be created via public registration")
        if role_str in ("viewer", "critic"):
            return RegisterRole(role_str)
        raise ValueError("Role must be 'viewer' or 'critic'")


# Alias for RegisterRequest
RegisterRequest = UserCreate


class UserResponse(UserBase):
    """
    User response schema.
    Inherits username and email from UserBase, adds id and role.
    MUST NOT contain password or password_hash.
    """

    id: uuid.UUID = Field(..., description="Unique user identifier")
    role: str = Field(default="viewer", description="User role in the system")
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
    role: str = Field(default="viewer", description="Authenticated user role")
    username: str | None = Field(default=None, description="Authenticated username")
    email: str | None = Field(default=None, description="Authenticated user email")


class AdminStatsResponse(BaseSchema):
    """
    Schema for platform-wide administrative statistics.
    """

    total_films: int = Field(..., description="Total film count")
    total_reviews: int = Field(..., description="Total review count")
    average_rating: float | None = Field(default=None, description="Overall average rating across all reviews")
    top_reviewer: str | None = Field(
        default=None, description="Username of the user who has submitted the most reviews"
    )


class LogoutRequest(BaseSchema):
    """
    Optional schema for logout request allowing explicit refresh token submission.
    """

    refresh_token: str | None = Field(default=None, description="Optional refresh token to revoke")


class LogoutResponse(BaseSchema):
    """
    Schema for logout confirmation response.
    """

    message: str = Field(default="Successfully logged out", description="Logout confirmation message")
    status: str = Field(default="success", description="Status indicator")
