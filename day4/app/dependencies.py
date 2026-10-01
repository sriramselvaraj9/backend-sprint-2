from collections.abc import AsyncGenerator
from typing import Optional
import uuid
from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, settings
from app.database import SessionLocal


def get_config() -> Settings:
    """
    Dependency providing the centralized configuration object.
    Routes that need configuration inject this via Depends(get_config).
    """
    return settings


# ---------------------------------------------------------
# 5 & 6. Replace Day 3 Placeholder with Real AsyncSession
# ---------------------------------------------------------
async def get_db(
    config: Settings = Depends(get_config)
) -> AsyncGenerator[AsyncSession, None]:
    """
    Asynchronous database session dependency scoped to a single HTTP request.
    Replaces the Day 3 placeholder dependency with a real SQLAlchemy AsyncSession.
    Maintains the dependency chain by depending on get_config.
    Using 'async with SessionLocal()' ensures the session is automatically closed
    after the HTTP request finishes.
    """
    async with SessionLocal() as session:
        yield session


# Alias for get_session conforming to standard naming
get_session = get_db


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
