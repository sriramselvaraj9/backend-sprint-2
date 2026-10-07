from fastapi import APIRouter, Depends, status

from app.dependencies import get_auth_user_handler, get_current_user
from app.handlers.auth_user_handler import AuthUserHandler
from app.schemas.user import (
    AuthenticatedUser,
    LoginRequest,
    RefreshRequest,
    TokenResponse,
    UserCreate,
    UserResponse,
)

router = APIRouter(tags=["Auth / Users"])


# Public Registration Endpoint: POST /api/v1/auth/register
@router.post("/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    handler: AuthUserHandler = Depends(get_auth_user_handler),
) -> UserResponse:
    """
    Public registration endpoint.
    Creates a new user account with bcrypt password hash.
    """
    user = await handler.register_user(user_data)
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        created_at=user.created_at,
    )


# Public Login Endpoint: POST /api/v1/auth/login
@router.post("/auth/login", response_model=TokenResponse)
async def login(
    credentials: LoginRequest,
    handler: AuthUserHandler = Depends(get_auth_user_handler),
) -> TokenResponse:
    """
    Public login endpoint.
    Authenticates email + password and returns access_token + refresh_token.
    """
    return await handler.login(credentials)


# Public Refresh Endpoint: POST /api/v1/auth/refresh
@router.post("/auth/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_data: RefreshRequest,
    handler: AuthUserHandler = Depends(get_auth_user_handler),
) -> TokenResponse:
    """
    Public token refresh endpoint.
    Verifies refresh token, marks it as used, and issues a new access token.
    """
    return await handler.refresh_token(refresh_data)


# Protected Current User Profile Endpoint: GET /api/v1/users/me
@router.get("/users/me", response_model=UserResponse)
async def get_me(
    current_user: AuthenticatedUser = Depends(get_current_user),
    handler: AuthUserHandler = Depends(get_auth_user_handler),
) -> UserResponse:
    """
    Protected user profile endpoint.
    Requires a valid access token in Authorization header.
    """
    user = await handler.get_me(current_user)
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        created_at=user.created_at,
    )


# Protected Admin Stats Endpoint: GET /api/v1/admin/stats
@router.get("/admin/stats")
async def get_stats(
    current_user: AuthenticatedUser = Depends(get_current_user),
    handler: AuthUserHandler = Depends(get_auth_user_handler),
) -> dict:
    """
    Protected admin statistics endpoint.
    Requires a valid access token in Authorization header.
    """
    return await handler.get_admin_stats()
