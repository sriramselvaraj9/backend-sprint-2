from app.schemas.user import UserCreate, LoginRequest


async def register_user(user_data: UserCreate) -> dict:
    return {
        "id": 1,
        "name": user_data.name,
        "email": user_data.email
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
        "message": "User profile fetched successfully",
        "user": {
            "id": 1,
            "name": "sriram",
            "email": "srirammurthy12345@gmail.com",
            "role": "user"
        }
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





