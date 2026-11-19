"""
tests/unit/test_film_service.py

Unit tests for FilmService business operations and business rules.
Tests the service layer in strict isolation using mocked DAOs and caches,
ensuring real domain objects and domain exceptions are used without requiring
a running PostgreSQL or Redis instance.
"""
# creating films, soft-deleting rules, Redis cache hit/miss behavior, and review aggregate recalculation.
import uuid
from unittest.mock import AsyncMock

import pytest

from app.exceptions.domain import (
    FilmHasActiveReviewsError,
    FilmNotFoundError,
)
from app.models.film import Film
from app.models.review import Review
from app.schemas.film import FilmCreate, FilmYearRange
from app.services.film_service import FilmService

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Retrieval & Existence Tests
# ---------------------------------------------------------------------------


class TestFilmServiceGetById:
    """Verify FilmService.get_film_by_id business logic."""

    async def test_get_film_by_id_success(
        self,
        film_service: FilmService,
        mock_film_dao: AsyncMock,
        sample_film: Film,
    ) -> None:
        """Verify that an existing active film is returned successfully."""
        mock_film_dao.get_by_id.return_value = sample_film

        result = await film_service.get_film_by_id(sample_film.id)

        assert result == sample_film
        assert result.title == "Inception"
        mock_film_dao.get_by_id.assert_awaited_once_with(sample_film.id, active_only=True)

    async def test_get_film_by_id_not_found_raises_domain_error(
        self,
        film_service: FilmService,
        mock_film_dao: AsyncMock,
    ) -> None:
        """Verify that requesting a nonexistent or inactive film raises FilmNotFoundError."""
        missing_id = uuid.uuid4()
        mock_film_dao.get_by_id.return_value = None

        with pytest.raises(FilmNotFoundError) as exc_info:
            await film_service.get_film_by_id(missing_id)

        err = exc_info.value
        assert err.film_id == missing_id
        assert err.error_code == "FILM_NOT_FOUND"
        assert err.status_code == 404
        assert str(missing_id) in err.detail["film_id"]


# ---------------------------------------------------------------------------
# Creation & Modification Tests
# ---------------------------------------------------------------------------


class TestFilmServiceCreateAndUpdate:
    """Verify film creation and updating business logic and cache invalidation."""

    async def test_create_film_persists_and_invalidates_cache(
        self,
        film_service: FilmService,
        mock_film_dao: AsyncMock,
        mock_cache: AsyncMock,
    ) -> None:
        """Verify film persistence and immediate cache invalidation."""
        film_in = FilmCreate(
            title="Oppenheimer",
            release_year=2023,
            genre="Biography",
            director="Christopher Nolan",
        )
        saved_film = Film(
            id=uuid.uuid4(),
            title=film_in.title,
            release_year=film_in.release_year,
            genre=film_in.genre,
            director=film_in.director,
            is_active=True,
        )
        mock_film_dao.create.return_value = saved_film

        created = await film_service.create_film(film_in)

        assert created.id == saved_film.id
        assert created.title == "Oppenheimer"
        mock_film_dao.create.assert_awaited_once()
        mock_cache.invalidate.assert_awaited_once()

    async def test_update_film_success(
        self,
        film_service: FilmService,
        mock_film_dao: AsyncMock,
        mock_cache: AsyncMock,
        sample_film: Film,
    ) -> None:
        """Verify updating film fields and cache invalidation."""
        mock_film_dao.get_by_id.return_value = sample_film
        sample_film.title = "Inception (Extended Edition)"
        mock_film_dao.update.return_value = sample_film

        result = await film_service.update_film(
            sample_film.id,
            update_data={"title": "Inception (Extended Edition)"},
        )

        assert result.title == "Inception (Extended Edition)"
        mock_film_dao.update.assert_awaited_once()
        mock_cache.invalidate.assert_awaited_once()

    async def test_update_film_not_found_raises_domain_error(
        self,
        film_service: FilmService,
        mock_film_dao: AsyncMock,
        mock_cache: AsyncMock,
    ) -> None:
        """Verify that updating a nonexistent film raises FilmNotFoundError without invalidation."""
        missing_id = uuid.uuid4()
        mock_film_dao.get_by_id.return_value = None

        with pytest.raises(FilmNotFoundError) as exc_info:
            await film_service.update_film(missing_id, update_data={"title": "New Title"})

        assert exc_info.value.film_id == missing_id
        mock_film_dao.update.assert_not_awaited()
        mock_cache.invalidate.assert_not_awaited()


# ---------------------------------------------------------------------------
# Soft-Delete Business Rule Tests
# ---------------------------------------------------------------------------


class TestFilmServiceDeleteRules:
    """Verify the business rule: A film cannot be soft-deleted if it has active reviews."""

    async def test_delete_film_rejected_when_active_reviews_exist(
        self,
        film_service: FilmService,
        mock_film_dao: AsyncMock,
        mock_review_dao: AsyncMock,
        mock_cache: AsyncMock,
        sample_film: Film,
        sample_review: Review,
        critic_review: Review,
    ) -> None:
        """
        Business Rule: A film cannot be soft-deleted if it still has active reviews.
        Must raise FilmHasActiveReviewsError with film ID and active review count.
        """
        mock_film_dao.get_by_id.return_value = sample_film
        # Film has 2 active reviews
        mock_review_dao.list_by_film.return_value = [sample_review, critic_review]

        with pytest.raises(FilmHasActiveReviewsError) as exc_info:
            await film_service.delete_film(sample_film.id)

        err = exc_info.value
        assert err.film_id == sample_film.id
        assert err.active_review_count == 2
        assert err.error_code == "FILM_HAS_ACTIVE_REVIEWS"
        assert err.status_code == 409
        assert err.detail["film_id"] == str(sample_film.id)
        assert err.detail["active_review_count"] == 2

        # Ensure soft-delete was NOT called and cache was NOT invalidated
        mock_film_dao.soft_delete.assert_not_awaited()
        mock_cache.invalidate.assert_not_awaited()

    async def test_delete_film_succeeds_when_no_active_reviews(
        self,
        film_service: FilmService,
        mock_film_dao: AsyncMock,
        mock_review_dao: AsyncMock,
        mock_cache: AsyncMock,
        sample_film: Film,
    ) -> None:
        """Verify that a film with zero active reviews is soft-deleted and invalidates cache."""
        mock_film_dao.get_by_id.return_value = sample_film
        mock_review_dao.list_by_film.return_value = []  # No reviews
        sample_film.is_active = False
        mock_film_dao.soft_delete.return_value = sample_film

        deleted = await film_service.delete_film(sample_film.id)

        assert deleted.is_active is False
        mock_film_dao.soft_delete.assert_awaited_once_with(sample_film)
        mock_cache.invalidate.assert_awaited_once()

    async def test_delete_film_not_found_raises_domain_error(
        self,
        film_service: FilmService,
        mock_film_dao: AsyncMock,
        mock_review_dao: AsyncMock,
    ) -> None:
        """Verify that attempting to delete a nonexistent film raises FilmNotFoundError."""
        missing_id = uuid.uuid4()
        mock_film_dao.get_by_id.return_value = None

        with pytest.raises(FilmNotFoundError) as exc_info:
            await film_service.delete_film(missing_id)

        assert exc_info.value.film_id == missing_id
        mock_review_dao.list_by_film.assert_not_awaited()
        mock_film_dao.soft_delete.assert_not_awaited()


# ---------------------------------------------------------------------------
# Filter Delegation & Cache Logic Tests
# ---------------------------------------------------------------------------


class TestFilmServiceFilteringAndCache:
    """Verify filtering delegation and cache hit vs miss behavior."""

    async def test_filter_films_by_year_range_delegation(
        self,
        film_service: FilmService,
        mock_film_dao: AsyncMock,
        mock_cache: AsyncMock,
        sample_film: Film,
    ) -> None:
        """Verify that filter_films_by_year_range delegates properly with min/max year bounds."""
        year_range = FilmYearRange(start_year=2000, end_year=2015)
        mock_cache.get.return_value = None  # Cache miss
        mock_film_dao.list_films.return_value = [sample_film]

        results = await film_service.filter_films_by_year_range(year_range)

        assert len(results) == 1
        assert results[0] == sample_film
        mock_film_dao.list_films.assert_awaited_once_with(
            genre=None,
            from_year=2000,
            to_year=2015,
            director=None,
        )

    async def test_list_films_cache_hit_bypasses_dao(
        self,
        film_service: FilmService,
        mock_film_dao: AsyncMock,
        mock_cache: AsyncMock,
        sample_film: Film,
    ) -> None:
        """Verify that a Redis cache HIT returns cached data immediately without calling FilmDAO."""
        mock_cache.get.return_value = [sample_film]

        results = await film_service.list_films(genre="Sci-Fi")

        assert results == [sample_film]
        mock_cache.get.assert_awaited_once()
        mock_film_dao.list_films.assert_not_awaited()

    async def test_list_films_cache_miss_queries_dao_and_caches_result(
        self,
        film_service: FilmService,
        mock_film_dao: AsyncMock,
        mock_cache: AsyncMock,
        sample_film: Film,
    ) -> None:
        """Verify that a cache MISS queries FilmDAO and stores results into the cache."""
        mock_cache.get.return_value = None
        mock_film_dao.list_films.return_value = [sample_film]

        results = await film_service.list_films(genre="Sci-Fi")

        assert results == [sample_film]
        mock_film_dao.list_films.assert_awaited_once_with(
            genre="Sci-Fi",
            from_year=None,
            to_year=None,
            director=None,
        )
        mock_cache.set.assert_awaited_once()


# ---------------------------------------------------------------------------
# Aggregate Recalculation Tests
# ---------------------------------------------------------------------------


class TestFilmReviewAggregateRecalculation:
    """Verify aggregate recalculation business coordination."""

    async def test_recalculate_aggregates_updates_dao_and_invalidates_cache(
        self,
        film_service: FilmService,
        mock_review_dao: AsyncMock,
        mock_film_dao: AsyncMock,
        mock_cache: AsyncMock,
        sample_film: Film,
    ) -> None:
        """Verify that authoritative aggregates are queried from ReviewDAO and persisted to FilmDAO."""
        mock_review_dao.get_review_aggregates_by_film_id.return_value = (5, 8.4)
        sample_film.review_count = 5
        sample_film.average_rating = 8.4
        mock_film_dao.update_film_review_aggregates.return_value = sample_film

        result = await film_service.recalculate_film_review_aggregates(sample_film.id)

        assert result is not None
        assert result.review_count == 5
        assert result.average_rating == 8.4
        mock_review_dao.get_review_aggregates_by_film_id.assert_awaited_once_with(sample_film.id)
        mock_film_dao.update_film_review_aggregates.assert_awaited_once_with(
            film_id=sample_film.id,
            review_count=5,
            average_rating=8.4,
        )
        mock_cache.invalidate.assert_awaited_once_with("films:*")
