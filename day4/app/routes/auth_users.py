from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.handlers import auth_user_handler
from app.schemas.user import UserCreate, UserResponse, LoginRequest

router = APIRouter(tags=["Auth / Users"])


@router.post("/auth/register", response_model=UserResponse)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await auth_user_handler.handle_register(user_data, db=db)


@router.post("/auth/login")
async def login(credentials: LoginRequest) -> dict:
    return await auth_user_handler.handle_login(credentials)


@router.get("/users/me", response_model=UserResponse)
async def get_me() -> dict:
    return await auth_user_handler.handle_get_me()


@router.get("/admin/stats")
async def get_stats() -> dict:
    return await auth_user_handler.handle_get_admin_stats()
