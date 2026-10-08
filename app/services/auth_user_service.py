import logging
import uuid
from datetime import UTC, datetime, timedelta

from jose import JWTError

from app.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.daos.user_dao import UserDAO
from app.exceptions.domain import (
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from app.models.user import User
from app.schemas.user import LoginRequest, RefreshRequest, TokenResponse, UserCreate

logger = logging.getLogger("user_service")


class UserService:
    """
    Service layer for User and Authentication business operations.
    Receives UserDAO; contains NO direct database queries.
    """

    def __init__(
        self,
        user_dao: UserDAO,
    ) -> None:
        self.user_dao = user_dao

    async def get_by_email(self, email: str) -> User | None:
        """
        Lookup user by email through UserDAO.
        """
        return await self.user_dao.get_by_email(email)

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        """
        Lookup user by ID through UserDAO.
        """
        return await self.user_dao.get_by_id(user_id)

    async def register_user(self, user_data: UserCreate) -> User:
        """
        Register a new user:
        1. Check whether email already exists via UserDAO.
        2. Reject duplicate users with UserAlreadyExistsError.
        3. Hash password using bcrypt.
        4. Persist user with password hash via UserDAO.
        5. Never store or return plaintext password.
        """
        logger.info(f"Attempting registration for email: {user_data.email}")
        existing_user = await self.user_dao.get_by_email(user_data.email)
        if existing_user is not None:
            logger.warning(f"Registration rejected: email '{user_data.email}' already registered")
            raise UserAlreadyExistsError(
                email=user_data.email,
                message=f"User with email '{user_data.email}' already exists",
            )

        existing_username = await self.user_dao.get_by_username(user_data.username)
        if existing_username is not None:
            logger.warning(f"Registration rejected: username '{user_data.username}' already registered")
            raise UserAlreadyExistsError(
                username=user_data.username,
                message=f"User with username '{user_data.username}' already exists",
            )

        # Hash password with Passlib/bcrypt
        password_hash = hash_password(user_data.password)

        new_user = User(
            username=user_data.username,
            email=user_data.email,
            password_hash=password_hash,
            role=user_data.role if hasattr(user_data, "role") and user_data.role else "viewer",
        )
        created_user = await self.user_dao.create(new_user)
        logger.info(f"User '{created_user.username}' (ID: {created_user.id}, role: {created_user.role}) registered successfully")
        return created_user

    async def login_user(self, credentials: LoginRequest) -> TokenResponse:
        logger.info(f"Login attempt for email: {credentials.email}")
        user = await self.user_dao.get_by_email(credentials.email)
        if user is None or not verify_password(credentials.password, user.password_hash):
            logger.warning(f"Login failed: invalid credentials for email '{credentials.email}'")
            raise InvalidCredentialsError(message="Invalid credentials")

        # Create access token carrying sub, role, and username
        access_token = create_access_token(
            data={
                "sub": str(user.id),
                "role": user.role,
                "username": user.username,
                "email": user.email,
            }
        )

        # Create longer-lived refresh token
        refresh_token = create_refresh_token(
            data={
                "sub": str(user.id),
            }
        )

        logger.info(f"User '{user.username}' logged in successfully")
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
        )

    async def refresh_access_token(self, refresh_data: RefreshRequest) -> TokenResponse:
        token_str = refresh_data.refresh_token
        try:
            payload = decode_token(token_str)
        except JWTError:
            logger.warning("Refresh token verification failed: invalid signature or expired JWT")
            raise InvalidRefreshTokenError(message="Invalid or expired refresh token")

        token_type = payload.get("type")
        if token_type != "refresh":
            logger.warning(f"Invalid token type provided to /refresh: '{token_type}'")
            raise InvalidRefreshTokenError(message="Invalid token type: expected refresh token")

        user_id_str = payload.get("sub")
        if not user_id_str:
            raise InvalidRefreshTokenError(message="Invalid refresh token: missing subject claim")

        try:
            user_id = uuid.UUID(user_id_str)
        except ValueError:
            raise InvalidRefreshTokenError(message="Invalid refresh token: malformed user ID")

        # Fetch current user state
        user = await self.user_dao.get_by_id(user_id)
        if user is None:
            raise InvalidRefreshTokenError(message="User associated with refresh token no longer exists")

        # Issue new access token
        new_access_token = create_access_token(
            data={
                "sub": str(user.id),
                "role": user.role,
                "username": user.username,
                "email": user.email,
            }
        )

        logger.info(f"Issued new access token for user '{user.username}' (ID: {user.id})")
        return TokenResponse(
            access_token=new_access_token,
            token_type="bearer",
        )

    async def get_me(self, user_id: uuid.UUID) -> User:
        """
        Fetch profile data for the specified user ID from UserDAO.
        """
        user = await self.user_dao.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError(user_id=user_id, message="User not found")
        return user

    async def get_admin_stats(self) -> dict:
        """
        Fetch administrative statistics through UserDAO.
        """
        return await self.user_dao.get_admin_stats()
