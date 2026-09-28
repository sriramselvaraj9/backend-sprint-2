from app.services import auth_user_service
from app.schemas.user import UserCreate, LoginRequest


async def handle_register(user_data: UserCreate) -> dict:
    user_dict = user_data.model_dump()
    print(f"[DEBUG] Validated UserCreate registration (safe dump): {user_dict}")
    return await auth_user_service.register_user(user_data)


async def handle_login(credentials: LoginRequest) -> dict:
    return await auth_user_service.login_user(credentials)


async def handle_get_me() -> dict:
    return await auth_user_service.get_me()


async def handle_get_admin_stats() -> dict:
    return await auth_user_service.get_admin_stats()
