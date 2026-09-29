from app.schemas.user import UserCreate, LoginRequest


async def register_user(user_data: UserCreate) -> dict:
    """
    Simulates user creation. Returns internal record containing password,
    which will be safely filtered out by UserResponse (response_model).
    """
    return {
        "id": 1,
        "username": user_data.username,
        "email": user_data.email,
        "role": "user",
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
    """
    Simulates fetching current user. Internal data contains password,
    which will be safely stripped by UserResponse.
    """
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
