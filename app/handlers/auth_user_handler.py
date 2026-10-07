from app.models.user import User
from app.schemas.user import (
    AuthenticatedUser,
    LoginRequest,
    RefreshRequest,
    TokenResponse,
    UserCreate,
)
from app.services.auth_user_service import UserService


class AuthUserHandler:
    """
    Handler layer for Auth & User requests.
    Delegates to UserService; contains NO direct database queries.
    """

    def __init__(self, service: UserService) -> None:
        self.service = service

    async def register_user(self, user_data: UserCreate) -> User:
        return await self.service.register_user(user_data)

    async def login(self, credentials: LoginRequest) -> TokenResponse:
        return await self.service.login_user(credentials)

    async def refresh_token(self, refresh_data: RefreshRequest) -> TokenResponse:
        return await self.service.refresh_access_token(refresh_data)

    async def get_me(self, current_user: AuthenticatedUser) -> User:
        return await self.service.get_me(current_user.id)

    async def get_admin_stats(self) -> dict:
        return await self.service.get_admin_stats()
