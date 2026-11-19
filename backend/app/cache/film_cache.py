import json
import logging
from typing import Any

import redis.asyncio as redis

from app.core.config import settings
from app.schemas.film import FilmResponse

logger = logging.getLogger("film_cache")


class FilmCache:
    """
    Redis cache abstraction specifically for Film operations.
    Handles key generation, serialization/deserialization, TTL, and cache invalidation.
    Contains NO database queries, business rules, or authentication logic.
    """

    def __init__(self, redis_client: redis.Redis | None = None) -> None:
        self.redis_client = redis_client

    def build_key(
        self,
        genre: str | None = None,
        min_year: int | None = None,
        max_year: int | None = None,
        from_year: int | None = None,
        to_year: int | None = None,
        director: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
        cursor: str | None = None,
    ) -> str:
        """
        Builds a deterministic Redis cache key based on query filters and pagination parameters.
        Examples:
          - films:list
          - films:list:genre=action
          - films:list:genre=action:min_year=2020
          - films:list:min_year=2000:max_year=2020
          - films:list:page=2
          - films:list:page=2:page_size=20
          - films:list:cursor=xyz
        """
        parts = ["films:list"]
        if genre and genre.strip():
            parts.append(f"genre={genre.strip().lower()}")

        effective_from_year = from_year if from_year is not None else min_year
        if effective_from_year is not None:
            parts.append(f"min_year={effective_from_year}")

        effective_to_year = to_year if to_year is not None else max_year
        if effective_to_year is not None:
            parts.append(f"max_year={effective_to_year}")

        if director and director.strip():
            parts.append(f"director={director.strip().lower()}")

        if cursor is not None:
            parts.append(f"cursor={cursor}")
            if page_size is not None and page_size != 10:
                parts.append(f"page_size={page_size}")
        else:
            if page is not None and page != 1:
                parts.append(f"page={page}")
            if page_size is not None and page_size != 10:
                parts.append(f"page_size={page_size}")

        return ":".join(parts)

    def build_count_key(
        self,
        genre: str | None = None,
        min_year: int | None = None,
        max_year: int | None = None,
        from_year: int | None = None,
        to_year: int | None = None,
        director: str | None = None,
    ) -> str:
        """
        Builds a deterministic Redis cache key for the total film count based on filters.
        """
        parts = ["films:count"]
        if genre and genre.strip():
            parts.append(f"genre={genre.strip().lower()}")

        effective_from_year = from_year if from_year is not None else min_year
        if effective_from_year is not None:
            parts.append(f"min_year={effective_from_year}")

        effective_to_year = to_year if to_year is not None else max_year
        if effective_to_year is not None:
            parts.append(f"max_year={effective_to_year}")

        if director and director.strip():
            parts.append(f"director={director.strip().lower()}")

        return ":".join(parts)

    async def get_count(self, key: str) -> int | None:
        """
        Retrieve cached film count by key.
        """
        if self.redis_client is None:
            return None

        try:
            val = await self.redis_client.get(key)
            if val is not None:
                logger.info(f"Redis cache HIT for count key: '{key}'")
                return int(val)
        except (redis.RedisError, ValueError) as e:
            logger.warning(f"Redis cache lookup error for count key '{key}': {e}")

        return None

    async def set_count(
        self,
        key: str,
        count: int,
        ttl: int | None = None,
    ) -> None:
        """
        Cache total film count in Redis with TTL.
        """
        if self.redis_client is None:
            return

        try:
            cache_ttl = ttl if ttl is not None else settings.REDIS_CACHE_TTL
            await self.redis_client.set(key, str(count), ex=cache_ttl)
            logger.info(f"Cached film count ({count}) in Redis with TTL {cache_ttl}s (key: '{key}')")
        except redis.RedisError as e:
            logger.warning(f"Failed to cache film count in Redis for key '{key}': {e}")

    async def get(self, key: str) -> list[FilmResponse] | None:
        """
        Retrieve cached film list by key.
        Returns deserialized list of FilmResponse objects, or None on cache miss / error.
        """
        if self.redis_client is None:
            return None

        try:
            cached_str = await self.redis_client.get(key)
            if cached_str is not None:
                logger.info(f"Redis cache HIT for key: '{key}'")
                raw_items = json.loads(cached_str)
                return [FilmResponse.model_validate(item) for item in raw_items]
        except (redis.RedisError, json.JSONDecodeError) as e:
            logger.warning(f"Redis cache lookup error for key '{key}': {e}")

        return None

    async def set(
        self,
        key: str,
        films: list[Any],
        ttl: int | None = None,
    ) -> None:
        """
        Serialize and cache film list in Redis with TTL.
        Defaults to settings.REDIS_CACHE_TTL if ttl is not explicitly provided.
        """
        if self.redis_client is None:
            return

        try:
            cache_ttl = ttl if ttl is not None else settings.REDIS_CACHE_TTL
            serialized = [FilmResponse.model_validate(f).model_dump(mode="json") for f in films]
            await self.redis_client.set(
                key,
                json.dumps(serialized),
                ex=cache_ttl,
            )
            logger.info(f"Cached {len(films)} films in Redis with TTL {cache_ttl}s (key: '{key}')")
        except redis.RedisError as e:
            logger.warning(f"Failed to cache films in Redis for key '{key}': {e}")

    async def get_cursor(self, key: str) -> tuple[list[FilmResponse], str | None] | None:
        """
        Retrieve cached cursor-paginated result (items, next_cursor) by key.
        """
        if self.redis_client is None:
            return None

        try:
            cached_str = await self.redis_client.get(key)
            if cached_str is not None:
                logger.info(f"Redis cache HIT for cursor key: '{key}'")
                payload = json.loads(cached_str)
                raw_items = payload.get("items", [])
                items = [FilmResponse.model_validate(item) for item in raw_items]
                next_cursor = payload.get("next_cursor")
                return items, next_cursor
        except (redis.RedisError, json.JSONDecodeError) as e:
            logger.warning(f"Redis cache lookup error for cursor key '{key}': {e}")

        return None

    async def set_cursor(
        self,
        key: str,
        films: list[Any],
        next_cursor: str | None,
        ttl: int | None = None,
    ) -> None:
        """
        Cache cursor-paginated result (items, next_cursor) in Redis with TTL.
        """
        if self.redis_client is None:
            return

        try:
            cache_ttl = ttl if ttl is not None else settings.REDIS_CACHE_TTL
            serialized = [FilmResponse.model_validate(f).model_dump(mode="json") for f in films]
            payload = {
                "items": serialized,
                "next_cursor": next_cursor,
            }
            await self.redis_client.set(
                key,
                json.dumps(payload),
                ex=cache_ttl,
            )
            logger.info(f"Cached {len(films)} cursor films in Redis with TTL {cache_ttl}s (key: '{key}')")
        except redis.RedisError as e:
            logger.warning(f"Failed to cache cursor films in Redis for key '{key}': {e}")

    async def invalidate(self, pattern: str = "films:*") -> None:
        """
        Invalidates all film cache entries in Redis matching pattern (defaults to 'films:*').
        """
        if self.redis_client is None:
            return

        try:
            keys = await self.redis_client.keys(pattern)
            if keys:
                await self.redis_client.delete(*keys)
                logger.info(f"Invalidated {len(keys)} film cache entries in Redis (pattern: '{pattern}')")
        except redis.RedisError as e:
            logger.warning(f"Failed to invalidate film cache in Redis: {e}")
