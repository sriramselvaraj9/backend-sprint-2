from app.daos import user_dao
from app.schemas.user import UserCreate, LoginRequest


async def register_user(user_data: UserCreate) -> dict:
    return await user_dao.register_user(user_data)


async def login_user(credentials: LoginRequest) -> dict:
    return await user_dao.login_user(credentials)


async def get_me() -> dict:
    return await user_dao.get_me()


async def get_admin_stats() -> dict:
    return await user_dao.get_admin_stats()
