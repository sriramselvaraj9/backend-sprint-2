"""
tests/integration/conftest.py

Shared pytest fixtures and configuration for integration testing.
Provides:
- An isolated in-memory SQLite database using SQLAlchemy's async engine (sqlite+aiosqlite).
- Schema creation once per test session and disposal on teardown.
- Strict test isolation by cleaning table data between tests.
- PRAGMA foreign_keys = ON enforcement for SQLite.
- FastAPI dependency overrides for database session and Redis.
- Reusable HTTPX AsyncClient using ASGITransport.
- Test user seeds and JWT authentication token helpers.
"""

import fnmatch
import uuid
from collections.abc import AsyncGenerator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app import dependencies
from app.core.database import Base
from app.core.security import create_access_token, hash_password
from app.main import app as fastapi_app
from app.models.film import Film
from app.models.review import Review
from app.models.user import User
from app.models.watchlist import Watchlist
from app.schemas.user import UserRole

# Ensure models are loaded into Base metadata
__all_models__ = [Film, Review, User, Watchlist]


# ---------------------------------------------------------------------------
# In-Memory Fake Redis
# ---------------------------------------------------------------------------
class FakeRedis:
    """
    Lightweight in-memory async Redis simulation.
    Allows UserService and FilmCache to operate in integration tests
    without requiring a running Redis server or incurring connection timeouts.
    """

    def __init__(self) -> None:
        self._data: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._data.get(key)

    async def set(self, key: str, value: Any, ex: int | None = None) -> bool:
        self._data[key] = str(value)
        return True

    async def delete(self, *keys: str) -> int:
        count = 0
        for k in keys:
            if k in self._data:
                del self._data[k]
                count += 1
        return count

    async def keys(self, pattern: str = "*") -> list[str]:
        return [k for k in self._data if fnmatch.fnmatch(k, pattern)]

    async def aclose(self) -> None:
        self._data.clear()


@pytest.fixture(scope="session")
def fake_redis() -> FakeRedis:
    """Provide a session-scoped in-memory Redis client."""
    return FakeRedis()


# ---------------------------------------------------------------------------
# Isolated SQLite Test Database
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def test_engine() -> AsyncEngine:
    """
    Create a dedicated asynchronous in-memory SQLite test engine.
    Uses StaticPool so that multiple concurrent connections access the same in-memory DB.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection: Any, connection_record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


@pytest.fixture(scope="session")
def test_session_factory(test_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Provide an async_sessionmaker bound to the isolated SQLite test engine."""
    return async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


@pytest.fixture(scope="session", autouse=True)
async def init_test_database(test_engine: AsyncEngine) -> AsyncGenerator[None]:
    """
    Create database schema once for the entire test session.
    Drops the schema and disposes the test engine on session teardown.
    """
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await test_engine.dispose()


@pytest.fixture
async def db_session(
    test_engine: AsyncEngine,
    test_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession]:
    """
    Function-scoped AsyncSession fixture providing database isolation.
    Resets all table data between tests in reverse dependency order.
    """
    # Clean up before test begins
    async with test_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())

    async with test_session_factory() as session:
        yield session

    # Clean up after test finishes
    async with test_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())


# ---------------------------------------------------------------------------
# HTTPX AsyncClient with Dependency Overrides
# ---------------------------------------------------------------------------
@pytest.fixture
async def client(
    test_engine: AsyncEngine,
    test_session_factory: async_sessionmaker[AsyncSession],
    fake_redis: FakeRedis,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncGenerator[AsyncClient]:
    """
    Reusable HTTPX AsyncClient fixture.
    Configured with ASGITransport, base_url='http://test', and database dependency overrides.
    Ensures dependency overrides are strictly restored on fixture teardown.
    """
    # Clean data state before each request-based test
    async with test_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())
    fake_redis._data.clear()

    async def _test_get_session() -> AsyncGenerator[AsyncSession]:
        async with test_session_factory() as session:
            yield session

    async def _test_get_redis() -> FakeRedis:
        return fake_redis

    # Ensure background tasks (such as aggregate recalculation) also use test SQLite DB
    import app.core.database

    monkeypatch.setattr(app.core.database, "SessionLocal", test_session_factory)

    # Save existing overrides
    saved_overrides = dict(fastapi_app.dependency_overrides)

    fastapi_app.dependency_overrides[dependencies.get_session] = _test_get_session
    fastapi_app.dependency_overrides[dependencies.get_db] = _test_get_session
    fastapi_app.dependency_overrides[app.core.database.get_session] = _test_get_session
    fastapi_app.dependency_overrides[dependencies.get_redis] = _test_get_redis

    transport = ASGITransport(app=fastapi_app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    finally:
        fastapi_app.dependency_overrides = saved_overrides
        # Clean up database after test
        async with test_engine.begin() as conn:
            for table in reversed(Base.metadata.sorted_tables):
                await conn.execute(table.delete())


# ---------------------------------------------------------------------------
# Authentication & Test User Helpers
# ---------------------------------------------------------------------------
def auth_headers(token: str) -> dict[str, str]:
    """Construct an HTTP Authorization header containing the Bearer token."""
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def make_token():
    """Helper to generate valid JWT access tokens with specified sub, role, username, email."""

    def _generate(
        user_id: uuid.UUID | str,
        role: str = "viewer",
        username: str = "testuser",
        email: str = "testuser@example.com",
    ) -> str:
        return create_access_token(
            data={
                "sub": str(user_id),
                "role": role,
                "username": username,
                "email": email,
            }
        )

    return _generate


@pytest.fixture
async def create_user(test_session_factory: async_sessionmaker[AsyncSession]):
    """Helper fixture to insert and commit a user directly into the isolated test database."""

    async def _create(
        username: str = "user",
        email: str = "user@example.com",
        password: str = "password123",
        role: str = UserRole.VIEWER.value,
    ) -> User:
        async with test_session_factory() as session:
            user = User(
                id=uuid.uuid4(),
                username=username,
                email=email,
                password_hash=hash_password(password),
                role=role,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return user

    return _create


@pytest.fixture
async def create_film(test_session_factory: async_sessionmaker[AsyncSession]):
    """Helper fixture to insert and commit a film directly into the isolated test database."""

    async def _create(
        title: str = "Test Movie",
        release_year: int = 2021,
        genre: str = "Sci-Fi",
        director: str = "Denis Villeneuve",
        is_active: bool = True,
    ) -> Film:
        async with test_session_factory() as session:
            film = Film(
                id=uuid.uuid4(),
                title=title,
                release_year=release_year,
                genre=genre,
                director=director,
                is_active=is_active,
            )
            session.add(film)
            await session.commit()
            await session.refresh(film)
            return film

    return _create


@pytest.fixture
async def admin_user(create_user) -> User:
    """Create a persistent Admin user in the test database."""
    return await create_user(
        username="admin_test",
        email="admin_test@example.com",
        password="AdminPassword123!",
        role=UserRole.ADMIN.value,
    )


@pytest.fixture
async def critic_user(create_user) -> User:
    """Create a persistent Critic user in the test database."""
    return await create_user(
        username="critic_test",
        email="critic_test@example.com",
        password="CriticPassword123!",
        role=UserRole.CRITIC.value,
    )


@pytest.fixture
async def second_critic_user(create_user) -> User:
    """Create a second persistent Critic user in the test database for ownership tests."""
    return await create_user(
        username="critic_two",
        email="critic_two@example.com",
        password="CriticPassword123!",
        role=UserRole.CRITIC.value,
    )


@pytest.fixture
async def viewer_user_db(create_user) -> User:
    """Create a persistent Viewer user in the test database."""
    return await create_user(
        username="viewer_test",
        email="viewer_test@example.com",
        password="ViewerPassword123!",
        role=UserRole.VIEWER.value,
    )


@pytest.fixture
def admin_token(admin_user: User, make_token) -> str:
    """Return a valid JWT access token for admin_user."""
    return make_token(
        user_id=admin_user.id,
        role=admin_user.role,
        username=admin_user.username,
        email=admin_user.email,
    )


@pytest.fixture
def critic_token(critic_user: User, make_token) -> str:
    """Return a valid JWT access token for critic_user."""
    return make_token(
        user_id=critic_user.id,
        role=critic_user.role,
        username=critic_user.username,
        email=critic_user.email,
    )


@pytest.fixture
def second_critic_token(second_critic_user: User, make_token) -> str:
    """Return a valid JWT access token for second_critic_user."""
    return make_token(
        user_id=second_critic_user.id,
        role=second_critic_user.role,
        username=second_critic_user.username,
        email=second_critic_user.email,
    )


@pytest.fixture
def viewer_token(viewer_user_db: User, make_token) -> str:
    """Return a valid JWT access token for viewer_user_db."""
    return make_token(
        user_id=viewer_user_db.id,
        role=viewer_user_db.role,
        username=viewer_user_db.username,
        email=viewer_user_db.email,
    )
