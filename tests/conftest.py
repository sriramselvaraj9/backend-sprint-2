"""
tests/conftest.py

Shared pytest fixtures for the Film Review Platform unit testing suite.
Provides typed, lightweight, isolated domain models (Film, User, Review)
and mocked DAOs/services using plain Python objects without requiring
a PostgreSQL database, Redis instance, or network connection.

Fixture Discovery Note:
Pytest automatically discovers this conftest.py file in the root tests directory.
Any fixture defined here is injected into test functions by matching parameter
names (e.g. `def test_something(sample_film): ...`) without requiring explicit
Python imports.
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from app.cache.film_cache import FilmCache
from app.daos.film_dao import FilmDAO
from app.daos.review_dao import ReviewDAO
from app.daos.user_dao import UserDAO
from app.models.film import Film
from app.models.review import Review
from app.models.user import User
from app.schemas.user import UserRole
from app.services.film_service import FilmService
from app.services.review_service import ReviewService

# ---------------------------------------------------------------------------
# Film Fixtures (function-scoped for strict test isolation)
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_film() -> Film:
    """Provide a standard, active Film model instance with realistic test data."""
    return Film(
        id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        title="Inception",
        release_year=2010,
        genre="Sci-Fi",
        director="Christopher Nolan",
        is_active=True,
        review_count=0,
        average_rating=None,
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def second_film() -> Film:
    """Provide an alternate active Film model instance."""
    return Film(
        id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
        title="Interstellar",
        release_year=2014,
        genre="Sci-Fi",
        director="Christopher Nolan",
        is_active=True,
        review_count=0,
        average_rating=None,
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def inactive_film() -> Film:
    """Provide a soft-deleted / inactive Film model instance."""
    return Film(
        id=uuid.UUID("33333333-3333-3333-3333-333333333333"),
        title="Archived Classic",
        release_year=1995,
        genre="Drama",
        director="Jane Doe",
        is_active=False,
        review_count=0,
        average_rating=None,
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def film_with_reviews() -> Film:
    """Provide an active Film model instance that already has associated reviews."""
    return Film(
        id=uuid.UUID("44444444-4444-4444-4444-444444444444"),
        title="The Dark Knight",
        release_year=2008,
        genre="Action",
        director="Christopher Nolan",
        is_active=True,
        review_count=3,
        average_rating=9.1,
        created_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# User Fixtures (Viewer, Critic, Admin roles)
# ---------------------------------------------------------------------------


@pytest.fixture
def viewer_user() -> User:
    """Provide a standard platform member with the 'viewer' role."""
    return User(
        id=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        username="viewer_john",
        email="john@example.com",
        password_hash="mocked_hashed_password_1",
        role=UserRole.VIEWER.value,
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def second_viewer_user() -> User:
    """Provide a second platform member with the 'viewer' role for ownership mismatch tests."""
    return User(
        id=uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
        username="viewer_sarah",
        email="sarah@example.com",
        password_hash="mocked_hashed_password_2",
        role=UserRole.VIEWER.value,
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def critic_user() -> User:
    """Provide a verified user with the 'critic' role."""
    return User(
        id=uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"),
        username="critic_roger",
        email="roger@example.com",
        password_hash="mocked_hashed_password_3",
        role=UserRole.CRITIC.value,
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def admin_user() -> User:
    """Provide an administrative user with the 'admin' role."""
    return User(
        id=uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd"),
        username="admin_alice",
        email="admin@example.com",
        password_hash="mocked_hashed_password_4",
        role=UserRole.ADMIN.value,
        created_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# Review Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_review(sample_film: Film, viewer_user: User) -> Review:
    """Provide a realistic Review instance authored by viewer_user for sample_film."""
    return Review(
        id=uuid.UUID("99999999-9999-9999-9999-999999999999"),
        film_id=sample_film.id,
        user_id=viewer_user.id,
        rating=9,
        body="Mind-bending concept with incredible direction and musical score.",
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def critic_review(sample_film: Film, critic_user: User) -> Review:
    """Provide a realistic Review instance authored by critic_user for sample_film."""
    return Review(
        id=uuid.UUID("88888888-8888-8888-8888-888888888888"),
        film_id=sample_film.id,
        user_id=critic_user.id,
        rating=10,
        body="An intricate cinematic triumph that rewards repeated viewings.",
        created_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# Mock DAO and Service Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_film_dao() -> AsyncMock:
    """Provide a mock FilmDAO with asynchronous method support."""
    mock = AsyncMock(spec=FilmDAO)
    return mock


@pytest.fixture
def mock_review_dao() -> AsyncMock:
    """Provide a mock ReviewDAO with asynchronous method support."""
    mock = AsyncMock(spec=ReviewDAO)
    return mock


@pytest.fixture
def mock_user_dao() -> AsyncMock:
    """Provide a mock UserDAO with asynchronous method support."""
    mock = AsyncMock(spec=UserDAO)
    return mock


@pytest.fixture
def mock_cache() -> AsyncMock:
    """Provide a mock FilmCache that bypasses Redis."""
    mock = AsyncMock(spec=FilmCache)
    mock.get.return_value = None
    mock.get_count.return_value = None
    mock.get_cursor.return_value = None
    mock.build_key.side_effect = lambda **kwargs: (
        f"mock_key:{':'.join(f'{k}={v}' for k, v in sorted(kwargs.items()) if v is not None)}"
    )
    mock.build_count_key.side_effect = lambda **kwargs: (
        f"mock_count_key:{':'.join(f'{k}={v}' for k, v in sorted(kwargs.items()) if v is not None)}"
    )
    return mock


@pytest.fixture
def film_service(mock_film_dao: AsyncMock, mock_review_dao: AsyncMock, mock_cache: AsyncMock) -> FilmService:
    """Provide a FilmService wired with mock DAOs and cache for isolated unit tests."""
    return FilmService(
        film_dao=mock_film_dao,
        review_dao=mock_review_dao,
        cache=mock_cache,
    )


@pytest.fixture
def review_service(mock_review_dao: AsyncMock, mock_film_dao: AsyncMock, mock_user_dao: AsyncMock) -> ReviewService:
    """Provide a ReviewService wired with mock DAOs for isolated unit tests."""
    return ReviewService(
        review_dao=mock_review_dao,
        film_dao=mock_film_dao,
        user_dao=mock_user_dao,
    )
