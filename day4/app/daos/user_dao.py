from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.user import UserCreate, LoginRequest


async def register_user(
    user_data: UserCreate,
    db: AsyncSession
) -> dict:
    """
    Creates user record in PostgreSQL using active db session.
    """
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        role="user"
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return {
        "id": new_user.id,
        "username": new_user.username,
        "email": new_user.email,
        "role": new_user.role,
        "password": "hashed_secret_password_do_not_expose"
    }


async def login_user(credentials: LoginRequest) -> dict:
    return {
        "message": "Login successful",
        "access_token": "mock_jwt_token_sample_12345",
        "token_type": "bearer",
        "email": credentials.email
    }


async def get_me() -> dict:
    return {
        "username": "sriram",
        "email": "srirammurthy12345@gmail.com",
        "role": "user",
        "password": "hashed_secret_password_do_not_expose"
    }


async def get_admin_stats() -> dict:
    return {
        "message": "Admin statistics fetched successfully",
        "stats": {
            "total_users": 150,
            "total_films": 42,
            "total_reviews": 320,
            "active_sessions": 12
        }
    }
