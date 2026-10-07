import uuid
from typing import Any

from fastapi import status


class DomainError(Exception):
    """
    Base domain exception for all domain business rule violations.
    Contains typed identifiers, standard error code, HTTP status code,
    and descriptive error messages with structured details.
    """

    def __init__(
        self,
        message: str,
        detail: dict[str, Any] | None = None,
        error_code: str = "DOMAIN_ERROR",
        status_code: int = status.HTTP_400_BAD_REQUEST,
    ) -> None:
        self.message = message
        self.detail = detail or {}
        self.error_code = error_code
        self.status_code = status_code
        super().__init__(self.message)


class ReviewAlreadyExistsError(DomainError):
    """
    Raised when a user attempts to submit more than one review for the same film.
    Business Rule: One review per user per film.
    """

    def __init__(
        self,
        film_id: uuid.UUID | str | int,
        user_id: uuid.UUID | str | int,
        message: str = "User has already submitted a review for this film",
    ) -> None:
        self.film_id = film_id
        self.user_id = user_id
        super().__init__(
            message=message,
            detail={
                "film_id": str(film_id),
                "user_id": str(user_id),
            },
            error_code="REVIEW_ALREADY_EXISTS",
            status_code=status.HTTP_409_CONFLICT,
        )


class ReviewUnauthorisedError(DomainError):
    """
    Raised when a user attempts to update a review they did not author.
    Business Rule: Only the original reviewer can update a review.
    """

    def __init__(
        self,
        review_id: uuid.UUID | str | int,
        user_id: uuid.UUID | str | int,
        message: str = "Only the original reviewer can update this review",
    ) -> None:
        self.review_id = review_id
        self.user_id = user_id
        super().__init__(
            message=message,
            detail={
                "review_id": str(review_id),
                "user_id": str(user_id),
            },
            error_code="REVIEW_UNAUTHORISED",
            status_code=status.HTTP_403_FORBIDDEN,
        )


# Alias for alternative spelling
ReviewUnauthorizedError = ReviewUnauthorisedError


class FilmHasActiveReviewsError(DomainError):
    """
    Raised when an attempt is made to soft-delete a film that still has active reviews.
    Business Rule: A film cannot be soft-deleted if it still has active reviews.
    """

    def __init__(
        self,
        film_id: uuid.UUID | str | int,
        active_review_count: int | None = None,
        message: str = "Cannot delete film because it still has active reviews",
    ) -> None:
        self.film_id = film_id
        self.active_review_count = active_review_count
        detail: dict[str, Any] = {"film_id": str(film_id)}
        if active_review_count is not None:
            detail["active_review_count"] = active_review_count
        super().__init__(
            message=message,
            detail=detail,
            error_code="FILM_HAS_ACTIVE_REVIEWS",
            status_code=status.HTTP_409_CONFLICT,
        )


class FilmNotFoundError(DomainError):
    """
    Raised when a requested film is not found or has been soft-deleted.
    """

    def __init__(
        self,
        film_id: uuid.UUID | str | int,
        message: str | None = None,
    ) -> None:
        self.film_id = film_id
        msg = message or f"Film with ID {film_id} not found"
        super().__init__(
            message=msg,
            detail={"film_id": str(film_id)},
            error_code="FILM_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )


class ReviewNotFoundError(DomainError):
    """
    Raised when a requested review is not found.
    """

    def __init__(
        self,
        review_id: uuid.UUID | str | int,
        message: str | None = None,
    ) -> None:
        self.review_id = review_id
        msg = message or f"Review with ID {review_id} not found"
        super().__init__(
            message=msg,
            detail={"review_id": str(review_id)},
            error_code="REVIEW_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )


class UserNotFoundError(DomainError):
    """
    Raised when a requested user is not found.
    """

    def __init__(
        self,
        user_id: uuid.UUID | str | int,
        message: str | None = None,
    ) -> None:
        self.user_id = user_id
        msg = message or f"User with ID {user_id} not found"
        super().__init__(
            message=msg,
            detail={"user_id": str(user_id)},
            error_code="USER_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )


class UserAlreadyExistsError(DomainError):
    """
    Raised when registering a user with an email or username that is already in use.
    """

    def __init__(
        self,
        email: str | None = None,
        username: str | None = None,
        message: str = "User with given email or username already exists",
    ) -> None:
        self.email = email
        self.username = username
        detail: dict[str, Any] = {}
        if email:
            detail["email"] = email
        if username:
            detail["username"] = username
        super().__init__(
            message=message,
            detail=detail,
            error_code="USER_ALREADY_EXISTS",
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class InvalidCredentialsError(DomainError):
    """
    Raised when authentication credentials (email/password) are incorrect.
    Never exposes whether the email or password was the specific failure reason.
    """

    def __init__(
        self,
        message: str = "Invalid credentials",
    ) -> None:
        super().__init__(
            message=message,
            detail={},
            error_code="INVALID_CREDENTIALS",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class InvalidTokenError(DomainError):
    """
    Raised when an access token is missing, expired, malformed, or invalid.
    """

    def __init__(
        self,
        message: str = "Invalid or expired access token",
    ) -> None:
        super().__init__(
            message=message,
            detail={},
            error_code="INVALID_TOKEN",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class InvalidRefreshTokenError(DomainError):
    """
    Raised when a refresh token is invalid, expired, revoked, or already used.
    """

    def __init__(
        self,
        message: str = "Invalid, expired, or already used refresh token",
    ) -> None:
        super().__init__(
            message=message,
            detail={},
            error_code="INVALID_REFRESH_TOKEN",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
