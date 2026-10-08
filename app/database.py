from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

# ---------------------------------------------------------
# Async Database Engine
# ---------------------------------------------------------
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    echo=False,
)


# ---------------------------------------------------------
# Async Session Factory
# ---------------------------------------------------------
SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


# ---------------------------------------------------------
# Declarative Base
# ---------------------------------------------------------
class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------
# Database Table Creation
# ---------------------------------------------------------
async def init_db() -> None:
    """
    Creates missing tables from the SQLAlchemy metadata.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ---------------------------------------------------------
# Request-Scoped Session Dependency
# ---------------------------------------------------------
async def get_session() -> AsyncGenerator[AsyncSession]:
    """
    Dependency that provides an AsyncSession scoped to a single HTTP request.
    """
    async with SessionLocal() as session:
        yield session
