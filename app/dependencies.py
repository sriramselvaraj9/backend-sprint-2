import uuid
from collections.abc import AsyncGenerator

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, settings
from app.core.security import decode_token
from app.daos.film_dao import FilmDAO
from app.daos.review_dao import ReviewDAO
from app.daos.user_dao import UserDAO
from app.database import SessionLocal
from app.exceptions.domain import InvalidTokenError
from app.handlers.auth_user_handler import AuthUserHandler
from app.handlers.film_handler import FilmHandler
from app.handlers.review_handler import ReviewHandler
from app.logging_config import get_current_request_id, set_current_request_id
from app.schemas.user import AuthenticatedUser
from app.services.auth_user_service import UserService
from app.services.film_service import FilmService
from app.services.review_service import ReviewService

# OpenAPI Security Scheme for Swagger UI Authorize button & lock icons
http_bearer_scheme = HTTPBearer(auto_error=False)


def get_config() -> Settings:
    """
    Dependency providing the centralized configuration object.
    Routes that need configuration inject this via Depends(get_config).
    """
    return settings


async def get_db(
    config: Settings = Depends(get_config),
) -> AsyncGenerator[AsyncSession]:
    """
    Asynchronous database session dependency scoped to a single HTTP request.
    Using 'async with SessionLocal()' ensures the session is automatically closed
    after the HTTP request finishes.
    """
    async with SessionLocal() as session:
        yield session


# Alias for get_session conforming to standard naming
get_session = get_db


def get_trace_id(
    x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
) -> str:
    """
    Dependency providing a request trace identifier.
    Integrates with the centralized logging ContextVar.
    Reads existing context ID, or X-Request-ID header if present, or generates a new UUID.
    """
    ctx_id = get_current_request_id()
    if ctx_id:
        return ctx_id

    if x_request_id:
        set_current_request_id(x_request_id)
        return x_request_id

    new_id = str(uuid.uuid4())
    set_current_request_id(new_id)
    return new_id


# ---------------------------------------------------------
# DAO Dependencies
# ---------------------------------------------------------
def get_film_dao(
    session: AsyncSession = Depends(get_session),
) -> FilmDAO:
    """
    Provides a FilmDAO instance with an injected AsyncSession.
    """
    return FilmDAO(session)


def get_review_dao(
    session: AsyncSession = Depends(get_session),
) -> ReviewDAO:
    """
    Provides a ReviewDAO instance with an injected AsyncSession.
    """
    return ReviewDAO(session)


def get_user_dao(
    session: AsyncSession = Depends(get_session),
) -> UserDAO:
    """
    Provides a UserDAO instance with an injected AsyncSession.
    """
    return UserDAO(session)


# ---------------------------------------------------------
# Service Dependencies
# ---------------------------------------------------------
def get_film_service(
    film_dao: FilmDAO = Depends(get_film_dao),
    review_dao: ReviewDAO = Depends(get_review_dao),
) -> FilmService:
    """
    Provides a FilmService instance with injected FilmDAO and ReviewDAO.
    """
    return FilmService(film_dao=film_dao, review_dao=review_dao)


def get_review_service(
    review_dao: ReviewDAO = Depends(get_review_dao),
    film_dao: FilmDAO = Depends(get_film_dao),
    user_dao: UserDAO = Depends(get_user_dao),
) -> ReviewService:
    """
    Provides a ReviewService instance with injected ReviewDAO, FilmDAO, and UserDAO.
    """
    return ReviewService(
        review_dao=review_dao,
        film_dao=film_dao,
        user_dao=user_dao,
    )


def get_user_service(
    user_dao: UserDAO = Depends(get_user_dao),
) -> UserService:
    """
    Provides a UserService instance with injected UserDAO.
    """
    return UserService(user_dao=user_dao)


# ---------------------------------------------------------
# Handler Dependencies
# ---------------------------------------------------------
def get_film_handler(
    service: FilmService = Depends(get_film_service),
) -> FilmHandler:
    """
    Provides a FilmHandler instance with an injected FilmService.
    """
    return FilmHandler(service)


def get_review_handler(
    service: ReviewService = Depends(get_review_service),
) -> ReviewHandler:
    """
    Provides a ReviewHandler instance with an injected ReviewService.
    """
    return ReviewHandler(service)


def get_auth_user_handler(
    service: UserService = Depends(get_user_service),
) -> AuthUserHandler:
    """
    Provides an AuthUserHandler instance with an injected UserService.
    """
    return AuthUserHandler(service)


# ---------------------------------------------------------
# Authentication Dependency
# ---------------------------------------------------------
async def get_current_user(
    auth_credentials: HTTPAuthorizationCredentials | None = Depends(http_bearer_scheme),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> AuthenticatedUser:

    token: str | None = None
    if auth_credentials is not None:
        token = auth_credentials.credentials
    elif authorization:
        parts = authorization.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise InvalidTokenError(message="Invalid authorization header format. Expected 'Bearer <token>'")
        token = parts[1]

    if not token:
        raise InvalidTokenError(message="Authorization header is required")

    try:
        payload = decode_token(token)
    except JWTError:
        raise InvalidTokenError(message="Invalid or expired access token")

    # Ensure token is an access token, not a refresh token
    token_type = payload.get("type")
    if token_type != "access":
        raise InvalidTokenError(message="Invalid token type: expected access token")

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise InvalidTokenError(message="Invalid token: missing subject claim")

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise InvalidTokenError(message="Invalid token: malformed subject ID")

    return AuthenticatedUser(
        id=user_id,
        role=payload.get("role", "viewer"),
        username=payload.get("username"),
        email=payload.get("email"),
    )


# ---------------------------------------------------------
# Role Enforcement Dependency
# ---------------------------------------------------------
def require_role(*roles: str | list[str] | tuple[str, ...]):
    """
    Reusable FastAPI dependency for Role-Based Access Control (RBAC).
    Enforces that the authenticated user possesses one of the allowed roles (admin, critic, viewer).
    Raises HTTPException 403 Forbidden if the authenticated user's role is not authorized.
    """
    allowed_roles: set[str] = set()
    for r in roles:
        if isinstance(r, (list, tuple, set)):
            for item in r:
                allowed_roles.add(str(item).lower())
        else:
            allowed_roles.add(str(r).lower())

    async def role_checker(
        current_user: AuthenticatedUser = Depends(get_current_user),
    ) -> AuthenticatedUser:
        user_role = (current_user.role or "").lower()
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: insufficient role permissions",
            )
        return current_user

    return role_checker



