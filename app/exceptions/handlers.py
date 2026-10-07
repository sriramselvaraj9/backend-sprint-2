import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.exceptions.domain import (
    DomainError,
    FilmHasActiveReviewsError,
    FilmNotFoundError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    InvalidTokenError,
    ReviewAlreadyExistsError,
    ReviewNotFoundError,
    ReviewUnauthorisedError,
    ReviewUnauthorizedError,
    UserAlreadyExistsError,
    UserNotFoundError,
)

logger = logging.getLogger("exception_handler")

# Mapping from domain exception classes to corresponding HTTP status codes
DOMAIN_STATUS_MAP: dict[type[Exception], int] = {
    ReviewAlreadyExistsError: status.HTTP_409_CONFLICT,
    ReviewUnauthorisedError: status.HTTP_403_FORBIDDEN,
    ReviewUnauthorizedError: status.HTTP_403_FORBIDDEN,
    FilmHasActiveReviewsError: status.HTTP_409_CONFLICT,
    FilmNotFoundError: status.HTTP_404_NOT_FOUND,
    ReviewNotFoundError: status.HTTP_404_NOT_FOUND,
    UserNotFoundError: status.HTTP_404_NOT_FOUND,
    UserAlreadyExistsError: status.HTTP_400_BAD_REQUEST,
    InvalidCredentialsError: status.HTTP_401_UNAUTHORIZED,
    InvalidTokenError: status.HTTP_401_UNAUTHORIZED,
    InvalidRefreshTokenError: status.HTTP_401_UNAUTHORIZED,
}


async def domain_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Centralized exception handler that intercepts domain errors and converts them
    into standardized JSON error responses with proper HTTP status codes,
    descriptive error messages, typed error codes, and structured error details.
    """
    status_code = getattr(exc, "status_code", DOMAIN_STATUS_MAP.get(type(exc), status.HTTP_400_BAD_REQUEST))
    error_code = getattr(exc, "error_code", exc.__class__.__name__)
    message = getattr(exc, "message", str(exc))
    detail = getattr(exc, "detail", None)

    # Structured warning log for observability
    logger.warning(f"Domain exception occurred: [{error_code}] {exc.__class__.__name__} ({status_code}) - {message}")

    response_payload: dict[str, Any] = {
        "error_code": error_code,
        "type": exc.__class__.__name__,
        "status_code": status_code,
        "message": message,
        "detail": detail,
    }

    return JSONResponse(
        status_code=status_code,
        content=response_payload,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """
    Register all centralized domain exception handlers on the FastAPI application.
    A helper function called in app/main.py
    to register the exception handler on the FastAPI app instance.
    """
    # Register base DomainError as fallback
    app.add_exception_handler(DomainError, domain_exception_handler)

    # Register individual domain exceptions
    for exc_class in DOMAIN_STATUS_MAP:
        app.add_exception_handler(exc_class, domain_exception_handler)
