"""
tests/unit/test_redis_film_caching.py

Unit tests for Film Redis caching functionality using a mocked asynchronous Redis client.
Tests cache miss, cache hit, key generation, serialization, TTL enforcement, and DAO bypass.
"""

import json
from unittest.mock import AsyncMock

import pytest
import redis.asyncio as aioredis

from app.cache.film_cache import FilmCache
from app.core.config import settings
from app.models.film import Film
from app.schemas.film import FilmResponse
from app.services.film_service import FilmService

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_redis_client() -> AsyncMock:
    """Mock asynchronous Redis client conforming to redis.asyncio.Redis."""
    mock = AsyncMock(spec=aioredis.Redis)
    mock.get = AsyncMock(return_value=None)
    mock.set = AsyncMock(return_value=True)
    mock.delete = AsyncMock(return_value=1)
    mock.keys = AsyncMock(return_value=[])
    return mock


@pytest.fixture
def film_cache(mock_redis_client: AsyncMock) -> FilmCache:
    """FilmCache wired with the mocked asynchronous Redis client."""
    return FilmCache(redis_client=mock_redis_client)


@pytest.fixture
def film_service_with_redis(
    mock_film_dao: AsyncMock,
    mock_review_dao: AsyncMock,
    film_cache: FilmCache,
) -> FilmService:
    """FilmService instance wired with mock FilmDAO, ReviewDAO, and real FilmCache wrapping mock Redis."""
    return FilmService(
        film_dao=mock_film_dao,
        review_dao=mock_review_dao,
        cache=film_cache,
    )


class TestFilmRedisCaching:
    """Test suite for Film caching hit and miss operations using mock Redis client."""

    async def test_cache_miss_queries_dao_and_writes_to_redis(
        self,
        film_service_with_redis: FilmService,
        mock_film_dao: AsyncMock,
        mock_redis_client: AsyncMock,
        sample_film: Film,
    ) -> None:
        """ 
        Cache Miss Test:
        - Mock Redis client returns None for lookup.
        - Call film service method (list_films).
        - Verify FilmDAO is queried.
        - Verify result is serialized and written to Redis using correct key and expected TTL.
        - Verify returned result matches the DAO query result.
        """
        # 1. Configure mock Redis to return None on lookup (cache miss)
        mock_redis_client.get.return_value = None

        # 2. Configure mock DAO to return sample film
        mock_film_dao.list_films.return_value = [sample_film]

        expected_key = "films:list:genre=sci-fi"

        # 3. Call film service method
        result = await film_service_with_redis.list_films(genre="Sci-Fi")

        # 4. Verify Redis was queried for the exact cache key
        mock_redis_client.get.assert_awaited_once_with(expected_key)

        # 5. Verify database/DAO is queried
        mock_film_dao.list_films.assert_awaited_once_with(
            genre="Sci-Fi",
            from_year=None,
            to_year=None,
            director=None,
        )

        # 6. Verify result is serialized and written to Redis with correct cache key and TTL
        mock_redis_client.set.assert_awaited_once()
        call_args, call_kwargs = mock_redis_client.set.call_args
        assert call_args[0] == expected_key
        # Verify serialized JSON payload structure
        serialized_data = json.loads(call_args[1])
        assert isinstance(serialized_data, list)
        assert len(serialized_data) == 1
        assert serialized_data[0]["id"] == str(sample_film.id)
        assert serialized_data[0]["title"] == sample_film.title
        # Verify TTL
        assert call_kwargs.get("ex") == settings.REDIS_CACHE_TTL

        # 7. Verify returned result is correct
        assert result == [sample_film]

    async def test_cache_hit_returns_cached_data_and_bypasses_dao(
        self,
        film_service_with_redis: FilmService,
        mock_film_dao: AsyncMock,
        mock_redis_client: AsyncMock,
        sample_film: Film,
    ) -> None:
        """
        Cache Hit Test:
        - Configure Redis to return valid cached film data.
        - Call the same film service method.
        - Verify the correct cached result is returned.
        - Verify database/DAO is never queried.
        - Verify Redis is not unnecessarily written to again.
        """
        # 1. Prepare valid serialized cached film data matching FilmResponse schema
        expected_key = "films:list:genre=sci-fi"
        cached_payload = [
            FilmResponse.model_validate(sample_film).model_dump(mode="json")
        ]
        mock_redis_client.get.return_value = json.dumps(cached_payload)

        # 2. Call the same service method
        result = await film_service_with_redis.list_films(genre="Sci-Fi")

        # 3. Verify Redis get was called with correct key
        mock_redis_client.get.assert_awaited_once_with(expected_key)

        # 4. Verify returned result contains the correct deserialized film data
        assert len(result) == 1
        assert isinstance(result[0], FilmResponse)
        assert result[0].id == sample_film.id
        assert result[0].title == sample_film.title
        assert result[0].genre == sample_film.genre

        # 5. Verify database/DAO is never queried
        mock_film_dao.list_films.assert_not_awaited()

        # 6. Verify Redis is not unnecessarily written to again
        mock_redis_client.set.assert_not_awaited()

    async def test_cache_miss_and_hit_with_multi_filter_keys(
        self,
        film_service_with_redis: FilmService,
        mock_film_dao: AsyncMock,
        mock_redis_client: AsyncMock,
        sample_film: Film,
    ) -> None:
        """
        Verify cache key composition with multiple filters (genre, min_year, max_year, director).
        """
        mock_redis_client.get.return_value = None
        mock_film_dao.list_films.return_value = [sample_film]

        expected_key = "films:list:genre=action:min_year=2000:max_year=2024:director=nolan"

        await film_service_with_redis.list_films(
            genre="Action",
            min_year=2000,
            max_year=2024,
            director="Nolan",
        )

        mock_redis_client.get.assert_awaited_once_with(expected_key)
        mock_film_dao.list_films.assert_awaited_once_with(
            genre="Action",
            from_year=2000,
            to_year=2024,
            director="Nolan",
        )
        assert mock_redis_client.set.call_args[0][0] == expected_key

    async def test_paginated_films_cache_miss_queries_dao_and_caches_count_and_items(
        self,
        film_service_with_redis: FilmService,
        mock_film_dao: AsyncMock,
        mock_redis_client: AsyncMock,
        sample_film: Film,
    ) -> None:
        """
        Verify that list_films_paginated on cache miss queries FilmDAO for both items and count,
        and sets both keys in Redis with expected TTL.
        """
        mock_redis_client.get.return_value = None
        mock_film_dao.list_films.return_value = [sample_film]
        mock_film_dao.count_films.return_value = 1

        films, total, next_cursor = await film_service_with_redis.list_films_paginated(
            page=1,
            page_size=10,
            genre="Sci-Fi",
        )

        assert len(films) == 1
        assert total == 1
        assert next_cursor is None
        mock_film_dao.list_films.assert_awaited_once()
        mock_film_dao.count_films.assert_awaited_once()
        # Verify set was called for film list and count
        assert mock_redis_client.set.await_count == 2

    async def test_paginated_films_cache_hit_bypasses_dao(
        self,
        film_service_with_redis: FilmService,
        mock_film_dao: AsyncMock,
        mock_redis_client: AsyncMock,
        sample_film: Film,
    ) -> None:
        """
        Verify that list_films_paginated on cache hit returns cached items and count
        without querying FilmDAO.
        """
        cached_items = [FilmResponse.model_validate(sample_film).model_dump(mode="json")]

        async def _mock_get(key: str) -> str | None:
            if "count" in key:
                return "1"
            return json.dumps(cached_items)

        mock_redis_client.get.side_effect = _mock_get

        films, total, next_cursor = await film_service_with_redis.list_films_paginated(
            page=1,
            page_size=10,
            genre="Sci-Fi",
        )

        assert len(films) == 1
        assert total == 1
        assert next_cursor is None
        assert films[0].id == sample_film.id
        mock_film_dao.list_films.assert_not_awaited()
        mock_film_dao.count_films.assert_not_awaited()
        mock_redis_client.set.assert_not_awaited()


class TestFilmCacheFailureResilience:
    """Verify that FilmCache gracefully handles Redis network errors and data corruption."""

    async def test_get_handles_redis_error_gracefully(
        self,
        film_cache: FilmCache,
        mock_redis_client: AsyncMock,
    ) -> None:
        """Verify that RedisError during cache lookup logs a warning and returns None without raising."""
        mock_redis_client.get.side_effect = aioredis.RedisError("Connection reset by peer")

        val = await film_cache.get("films:list")
        assert val is None

    async def test_get_handles_corrupted_json_gracefully(
        self,
        film_cache: FilmCache,
        mock_redis_client: AsyncMock,
    ) -> None:
        """Verify that JSONDecodeError on corrupted cache data returns None without raising."""
        mock_redis_client.get.return_value = "not-valid-json-string-{"

        val = await film_cache.get("films:list")
        assert val is None

    async def test_set_handles_redis_error_gracefully(
        self,
        film_cache: FilmCache,
        mock_redis_client: AsyncMock,
        sample_film: Film,
    ) -> None:
        """Verify that RedisError during cache set logs warning and does not propagate exception."""
        mock_redis_client.set.side_effect = aioredis.RedisError("Write failure to Redis")

        # Must not raise
        await film_cache.set("films:list", [sample_film])

    async def test_service_falls_back_to_database_when_redis_fails(
        self,
        film_service_with_redis: FilmService,
        mock_film_dao: AsyncMock,
        mock_redis_client: AsyncMock,
        sample_film: Film,
    ) -> None:
        """
        Verify end-to-end resilience: When Redis throws an error, the service falls back
        to querying the database through FilmDAO and returns the database records seamlessly.
        """
        mock_redis_client.get.side_effect = aioredis.RedisError("Redis connection refused")
        mock_film_dao.list_films.return_value = [sample_film]

        results = await film_service_with_redis.list_films(genre="Sci-Fi")

        assert results == [sample_film]
        mock_film_dao.list_films.assert_awaited_once()


class TestCursorPaginationCaching:
    """Verify cursor pagination next_cursor generation, caching, and cache hits."""

    async def test_cursor_pagination_computes_next_cursor_and_caches_result(
        self,
        film_service_with_redis: FilmService,
        mock_film_dao: AsyncMock,
        mock_redis_client: AsyncMock,
        sample_film: Film,
        second_film: Film,
    ) -> None:
        """
        Verify that list_films_cursor with page_size=1 fetches page_size + 1 records from DAO,
        truncates to page_size, computes next_cursor from the extra record, and stores into cache.
        """
        from app.core.pagination import encode_cursor

        mock_redis_client.get.return_value = None
        # Return 2 records when page_size is 1 (len > page_size)
        mock_film_dao.list_films.return_value = [sample_film, second_film]

        films, next_cursor = await film_service_with_redis.list_films_cursor(
            cursor=None,
            page_size=1,
        )

        assert len(films) == 1
        assert films[0].id == sample_film.id
        assert next_cursor == encode_cursor(second_film.id)
        mock_film_dao.list_films.assert_awaited_once_with(
            genre=None,
            from_year=None,
            to_year=None,
            director=None,
            limit=2,
            cursor_id=None,
        )
        mock_redis_client.set.assert_awaited_once()

    async def test_cursor_pagination_cache_hit_returns_cached_cursor_data(
        self,
        film_service_with_redis: FilmService,
        mock_film_dao: AsyncMock,
        mock_redis_client: AsyncMock,
        sample_film: Film,
    ) -> None:
        """
        Verify that list_films_cursor on cache hit deserializes items and next_cursor
        and returns immediately without calling FilmDAO.
        """
        from app.core.pagination import encode_cursor

        valid_cursor = encode_cursor(sample_film.id)
        cached_payload = {
            "items": [FilmResponse.model_validate(sample_film).model_dump(mode="json")],
            "next_cursor": "encoded_next_cursor_token_123",
        }
        mock_redis_client.get.return_value = json.dumps(cached_payload)

        films, next_cursor = await film_service_with_redis.list_films_cursor(
            cursor=valid_cursor,
            page_size=1,
        )

        assert len(films) == 1
        assert films[0].id == sample_film.id
        assert next_cursor == "encoded_next_cursor_token_123"
        mock_film_dao.list_films.assert_not_awaited()
        mock_redis_client.set.assert_not_awaited()


