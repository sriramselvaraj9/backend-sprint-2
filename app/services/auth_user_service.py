import logging
import uuid

import redis.asyncio as redis
from jose import JWTError

from app.core.config import settings
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
    Receives UserDAO and Redis client; coordinates DB persistence and Redis token lifecycle.
    Contains NO direct database queries.
    """

    def __init__(
        self,
        user_dao: UserDAO,
        redis_client: redis.Redis | None = None,
    ) -> None:
        self.user_dao = user_dao
        self.redis_client = redis_client

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
        logger.info(
            f"User '{created_user.username}' (ID: {created_user.id}, role: {created_user.role}) registered successfully"
        )
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

        # Store refresh token in Redis with TTL matching refresh token expiration
        if self.redis_client is not None:
            ttl_seconds = int(settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60)
            try:
                # Invalidate any previous token for this user so orphans don't accumulate
                previous_token = await self.redis_client.get(f"user_refresh_token:{user.id}")
                if previous_token:
                    await self.redis_client.delete(f"refresh_token:{previous_token}")

                # Store user ID string for O(1) lookup during refresh
                await self.redis_client.set(
                    f"refresh_token:{refresh_token}",
                    str(user.id),
                    ex=ttl_seconds,
                )
                # Store user mapping for session invalidation on logout
                await self.redis_client.set(
                    f"user_refresh_token:{user.id}",
                    refresh_token,
                    ex=ttl_seconds,
                )
                logger.info(f"Stored refresh token in Redis for user ID '{user.id}' (TTL: {ttl_seconds}s)")
            except redis.RedisError as e:
                logger.warning(f"Failed to store refresh token in Redis: {e}")

        logger.info(f"User '{user.username}' logged in successfully")
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
        )

    async def refresh_access_token(self, refresh_data: RefreshRequest) -> TokenResponse:
        """
        Validate refresh token (JWT validity + Redis existence) and issue a new access token.
        Provides server-side revocation: if token is absent from Redis, refresh is rejected.
        """
        token_str = refresh_data.refresh_token

        # 1. Validate JWT structure and signature/expiration
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

        # 2. Check Redis for server-side token existence (revocation check)
        if self.redis_client is not None:
            try:
                stored_session = await self.redis_client.get(f"refresh_token:{token_str}")
                if not stored_session:
                    logger.warning(f"Refresh token rejected: not found in Redis for user ID {user_id}")
                    raise InvalidRefreshTokenError(message="Invalid, expired, or revoked refresh token")
            except InvalidRefreshTokenError:
                raise
            except redis.RedisError as e:
                logger.warning(f"Redis error during refresh token validation: {e}")
                raise InvalidRefreshTokenError(message="Unable to verify refresh token")

        # 3. Fetch current user state from PostgreSQL
        user = await self.user_dao.get_by_id(user_id)
        if user is None:
            raise InvalidRefreshTokenError(message="User associated with refresh token no longer exists")

        # 4. Issue new access token
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

    async def logout_user(
        self,
        user_id: uuid.UUID,
        refresh_token: str | None = None,
    ) -> dict:
        """
        Log out user by deleting their refresh token from Redis, invalidating the session server-side.
        """
        logger.info(f"Logging out user ID: {user_id}")
        if self.redis_client is not None:
            try:
                # If explicit refresh token was provided in request, delete it
                if refresh_token:
                    await self.redis_client.delete(f"refresh_token:{refresh_token}")

                # Delete user-to-refresh-token mapping and corresponding refresh token
                stored_token = await self.redis_client.get(f"user_refresh_token:{user_id}")
                if stored_token:
                    await self.redis_client.delete(f"refresh_token:{stored_token}")
                    await self.redis_client.delete(f"user_refresh_token:{user_id}")

                logger.info(f"Revoked refresh token in Redis for user ID: {user_id}")
            except redis.RedisError as e:
                logger.warning(f"Redis error during logout for user {user_id}: {e}")

        return {
            "message": "Successfully logged out",
            "status": "success",
        }

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
