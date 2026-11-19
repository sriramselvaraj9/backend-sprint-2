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


class InvalidCursorError(DomainError):
    """
    Raised when an opaque pagination cursor is malformed or invalid.
    """

    def __init__(
        self,
        message: str = "Invalid pagination cursor",
        detail: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            detail=detail or {},
            error_code="INVALID_CURSOR",
            status_code=status.HTTP_400_BAD_REQUEST,
        )


# ---------------------------------------------------------------------------
# Storage Domain Exceptions (S3 / Floci Integration)
# ---------------------------------------------------------------------------


class StorageError(DomainError):
    """
    Base domain exception for all S3 and storage service operations.
    """

    def __init__(
        self,
        message: str = "Storage operation failed",
        detail: dict[str, Any] | None = None,
        error_code: str = "STORAGE_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
    ) -> None:
        super().__init__(
            message=message,
            detail=detail or {},
            error_code=error_code,
            status_code=status_code,
        )


class StorageValidationError(StorageError):
    """
    Raised when storage input or parameter validation fails (e.g., empty key,
    missing content type, non-positive file size, or disallowed MIME type).
    Maps to HTTP 400 Bad Request.
    """

    def __init__(
        self,
        message: str = "Storage validation failed",
        detail: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            detail=detail or {},
            error_code="STORAGE_VALIDATION_ERROR",
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class FileNotFoundError(StorageError):
    """
    Raised when a requested file or object cannot be found in storage.
    Named for parity with S3 client mapping and domain exception hierarchy.
    Maps to HTTP 404 Not Found.
    """

    def __init__(
        self,
        message: str = "File not found in storage",
        detail: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            detail=detail or {},
            error_code="STORAGE_OBJECT_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )


class BucketNotFoundError(StorageError):
    """
    Raised when the target S3 bucket does not exist (NoSuchBucket / BucketNotFound).
    Maps to HTTP 500 Internal Server Error.
    """

    def __init__(
        self,
        message: str = "Storage bucket not found",
        detail: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            detail=detail or {},
            error_code="STORAGE_BUCKET_NOT_FOUND",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class StoragePermissionDenied(StorageError):
    """
    Raised when S3 access is denied or credentials are invalid (AccessDenied / SignatureDoesNotMatch).
    Maps to HTTP 403 Forbidden.
    """

    def __init__(
        self,
        message: str = "Access denied to storage resource",
        detail: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            detail=detail or {},
            error_code="STORAGE_ACCESS_DENIED",
            status_code=status.HTTP_403_FORBIDDEN,
        )


class UploadFailedError(StorageError):
    """
    Raised when an S3 upload or presigned upload initialization fails unexpectedly.
    Maps to HTTP 500 Internal Server Error.
    """

    def __init__(
        self,
        message: str = "File upload failed",
        detail: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            detail=detail or {},
            error_code="STORAGE_UPLOAD_FAILED",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class StorageObjectNotFound(StorageError):
    """
    Raised when an object or file cannot be found in S3 storage (NoSuchKey / 404).
    Maps to HTTP 404 Not Found.
    """

    def __init__(
        self,
        file_id: str | uuid.UUID,
        message: str | None = None,
        key: str | None = None,
    ) -> None:
        self.file_id = str(file_id)
        self.key = key
        msg = message or f"Stored file '{file_id}' was not found in storage"
        detail: dict[str, Any] = {"file_id": str(file_id)}
        if key:
            detail["key"] = key
        super().__init__(
            message=msg,
            detail=detail,
            error_code="STORAGE_OBJECT_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )


class StorageBucketNotFound(StorageError):
    """
    Raised when the target S3 bucket does not exist (NoSuchBucket).
    Maps to HTTP 500 Internal Server Error (infrastructure failure).
    """

    def __init__(
        self,
        bucket_name: str,
        message: str | None = None,
    ) -> None:
        self.bucket_name = bucket_name
        msg = message or f"Target storage bucket '{bucket_name}' does not exist"
        super().__init__(
            message=msg,
            detail={"bucket_name": bucket_name},
            error_code="STORAGE_BUCKET_NOT_FOUND",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class StorageAccessDenied(StorageError):
    """
    Raised when access is denied to an S3 bucket or object (AccessDenied).
    Maps to HTTP 500 Internal Server Error (infrastructure failure).
    """

    def __init__(
        self,
        message: str = "Access denied to storage resource",
        detail: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            detail=detail or {},
            error_code="STORAGE_ACCESS_DENIED",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class StorageOperationError(StorageError):
    """
    Raised when an unexpected client error or unhandled S3 failure occurs.
    Maps to HTTP 500 Internal Server Error.
    """

    def __init__(
        self,
        message: str = "Storage operation failed",
        detail: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            detail=detail or {},
            error_code="STORAGE_OPERATION_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )



