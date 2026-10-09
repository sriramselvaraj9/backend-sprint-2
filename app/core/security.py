from datetime import UTC, datetime, timedelta
from typing import Any

from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings

# Tells Passlib to use the bcrypt algorithm
# Automatically marks older hashing schemes as deprecated if you ever add new ones later
pwd_context = CryptContext(schemes=["bcrypt"])  # CryptContext is a class from the passlib library

# JWT Signature Algorithm
JWT_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    """
    Hash a plaintext password using bcrypt.
    Never stores or returns plaintext passwords.
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plaintext password against a stored bcrypt hash.
    Returns True if matching, False otherwise.
    """
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """
    Create a signed JWT access token containing user identity and role.
    Defaults to the configured ACCESS_TOKEN_EXPIRE_MINUTES.
    """
    to_encode = data.copy()
    now_utc = datetime.now(UTC)
    if expires_delta:
        expire = now_utc + expires_delta
    else:
        expire = now_utc + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update(
        {
            "exp": expire,
            "iat": now_utc,
            "type": "access",
        }
    )
    return jwt.encode(to_encode, settings.TOKEN_SECRET_KEY, algorithm=JWT_ALGORITHM)


def create_refresh_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """
    Create a signed JWT refresh token with longer expiration.
    Defaults to the configured REFRESH_TOKEN_EXPIRE_DAYS.
    """
    to_encode = data.copy()
    now_utc = datetime.now(UTC)
    if expires_delta:
        expire = now_utc + expires_delta
    else:
        expire = now_utc + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode.update(
        {
            "exp": expire,
            "iat": now_utc,
            "type": "refresh",
        }
    )
    return jwt.encode(to_encode, settings.TOKEN_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and verify a JWT token signature and expiration.
    Raises jose.JWTError on invalid signature, malformed token, or expiration.
    """
    return jwt.decode(token, settings.TOKEN_SECRET_KEY, algorithms=[JWT_ALGORITHM])
