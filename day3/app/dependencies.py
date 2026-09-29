import uuid
from typing import Generator, Optional
from fastapi import Depends, Header

from app.config import Settings, settings


def get_config() -> Settings:
    """
    Dependency providing the centralized configuration object.
    Routes that need configuration inject this via Depends(get_config).
    """
    return settings

# Dependency Chaining
def get_db(config: Settings = Depends(get_config)) -> Generator[str, None, None]:    #it is a safe helper that gives the database to your routes and cleans it up when done.
    """
    Reusable placeholder database session dependency with yield and cleanup structure.
    Demonstrates a simple dependency chain (depends on get_config).
    Can be replaced later by a real async database session without changing route signatures.
    """
    db = "placeholder-db-session"                                                    #connection = connect(config.DATABASE_URL)
    try:
        yield db
    finally:
        pass


def get_trace_id(
    x_request_id: Optional[str] = Header(default=None, alias="X-Request-ID")
) -> str:
    """
    Dependency providing a request trace identifier.
    Reads X-Request-ID header if present, or generates a new UUID string if missing.
    """
    if x_request_id:
        return x_request_id
    return str(uuid.uuid4())
