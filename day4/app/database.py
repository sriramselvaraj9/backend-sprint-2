from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

# ---------------------------------------------------------
# 4. Async Database Engine
# ---------------------------------------------------------
# Create the SQLAlchemy asynchronous engine using postgresql+asyncpg:// driver.
# The connection string is retrieved from the centralized Settings object (not hardcoded).
# Connection pooling options:
# - pool_size: number of persistent connections to maintain
# - max_overflow: max additional temporary connections beyond pool_size
# - pool_pre_ping: tests liveness of connection before handing it out to prevent stale connection errors
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    echo=False, #echo=False: Set to True if you want to print every raw SQL query to your console for debugging, or False to keep the logs clean.
)

# ---------------------------------------------------------
# 5. Async Session Factory
# ---------------------------------------------------------
# async_sessionmaker produces new AsyncSession instances bound to the async engine.
# expire_on_commit=False ensures ORM model attributes remain accessible after commit
# without requiring an immediate refresh round trip.(Don't forget the object's data after commit)
SessionLocal = async_sessionmaker(
    bind=engine, 
    class_=AsyncSession,
    expire_on_commit=False
)


# ---------------------------------------------------------
# 1. Declarative Base
# ---------------------------------------------------------
# Base class for all SQLAlchemy 2.0 ORM models using DeclarativeBase.
#Central Catalog of All Tables (Base.metadata)
#Whenever a class inherits from Base, SQLAlchemy automatically registers that table into an internal registry called Base.metadata
class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------
# 9. Database Table Creation
# ---------------------------------------------------------
async def init_db() -> None:
    """
    Creates missing tables from the SQLAlchemy metadata.
    Because the project uses an async engine, connection.run_sync(...)
    bridges the asynchronous connection to the synchronous Base.metadata.create_all call.
    """
    # Import all models to ensure they are registered in Base.metadata before creating tables
    import app.models  

    async with engine.begin() as conn:
        # run_sync() executes a synchronous function (like create_all) using the async engine.
        await conn.run_sync(Base.metadata.create_all)



# ---------------------------------------------------------
# 5. Request-Scoped Session Dependency
# ---------------------------------------------------------
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency that provides an AsyncSession scoped to a single HTTP request.
    Using 'async with SessionLocal()' guarantees the session automatically closes
    when the request finishes.
    """
    async with SessionLocal() as session:
        yield session
