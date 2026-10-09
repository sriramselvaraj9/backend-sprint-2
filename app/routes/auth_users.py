from fastapi import APIRouter, Depends, status

from app.dependencies import (
    get_auth_user_handler,
    get_current_user,
    require_role,
)
from app.handlers.auth_user_handler import AuthUserHandler
from app.schemas.user import (
    AdminStatsResponse,
    AuthenticatedUser,
    LoginRequest,
    LogoutRequest,
    LogoutResponse,
    RefreshRequest,
    TokenResponse,
    UserCreate,
    UserResponse,
)

router = APIRouter(tags=["Auth / Users"])


# Public Registration Endpoint: POST /api/v1/auth/register
@router.post(
    "/auth/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Register a new user account with secure bcrypt password hashing and database persistence. Public endpoint. Passwords are never stored in plaintext and hashes are never returned. Admin accounts cannot be created via public registration.",
)
async def register(
    user_data: UserCreate,
    handler: AuthUserHandler = Depends(get_auth_user_handler),
) -> UserResponse:
    """
    Register a new user account with secure bcrypt password hashing and database persistence.
    Public endpoint. Passwords are never stored in plaintext and hashes are never returned.
    Admin accounts cannot be created via public registration.
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
@router.post("/auth/login", response_model=TokenResponse, summary="Login")
async def login(
    credentials: LoginRequest,
    handler: AuthUserHandler = Depends(get_auth_user_handler),
) -> TokenResponse:
    """
    Public login endpoint.
    Authenticates email + password, returns access_token + refresh_token,
    and stores refresh token in Redis with matching TTL.
    """
    return await handler.login(credentials)


# Public Refresh Endpoint: POST /api/v1/auth/refresh
@router.post("/auth/refresh", response_model=TokenResponse, summary="Refresh Token")
async def refresh_token(
    refresh_data: RefreshRequest,
    handler: AuthUserHandler = Depends(get_auth_user_handler),
) -> TokenResponse:
    """
    Public token refresh endpoint.
    Verifies JWT validity and server-side presence in Redis, then issues a new access token.
    """
    return await handler.refresh_token(refresh_data)


# Protected Logout Endpoint: POST /api/v1/auth/logout & POST /logout
@router.post("/auth/logout", response_model=LogoutResponse, summary="Logout")
@router.post("/logout", response_model=LogoutResponse, summary="Logout", include_in_schema=False)
async def logout(
    logout_data: LogoutRequest | None = None,
    current_user: AuthenticatedUser = Depends(get_current_user),
    handler: AuthUserHandler = Depends(get_auth_user_handler), 
) -> LogoutResponse:
    """
    Protected logout endpoint.
    Requires a valid access token. Revokes the user's refresh token by deleting it from Redis.
    """
    refresh_token = logout_data.refresh_token if logout_data is not None else None
    result = await handler.logout(user_id=current_user.id, refresh_token=refresh_token)
    return LogoutResponse(
        message=result.get("message", "Successfully logged out"),
        status=result.get("status", "success"),
    )


# Protected Current User Profile Endpoint: GET /api/v1/me
@router.get("/me", response_model=UserResponse, summary="Get Current User")
@router.get("/users/me", response_model=UserResponse, include_in_schema=False)
async def get_me(
    current_user: AuthenticatedUser = Depends(get_current_user),
    handler: AuthUserHandler = Depends(get_auth_user_handler),
) -> UserResponse:
    """
    Protected user profile endpoint.
    Accessible to all authenticated roles (Admin, Critic, Viewer).
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
@router.get("/admin/stats", response_model=AdminStatsResponse, summary="Get Admin Statistics")
@router.get("/admin/statistics", response_model=AdminStatsResponse, include_in_schema=False)
async def get_stats(
    current_user: AuthenticatedUser = Depends(require_role("admin")),
    handler: AuthUserHandler = Depends(get_auth_user_handler),
) -> AdminStatsResponse:
    """
    Protected admin statistics endpoint.
    Admin only: Critics and Viewers receive 403 Forbidden.
    """
    stats = await handler.get_admin_stats()
    return AdminStatsResponse(**stats)
