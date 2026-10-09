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
    ) -> str:
        """
        Builds a deterministic Redis cache key based on query filters.
        Examples:
          - films:list
          - films:list:genre=action
          - films:list:genre=action:min_year=2020
          - films:list:min_year=2000:max_year=2020
        """
        parts = ["films:list"]
        if genre and genre.strip():
            parts.append(f"genre={genre.strip().lower()}")
        if min_year is not None:
            parts.append(f"min_year={min_year}")
        if max_year is not None:
            parts.append(f"max_year={max_year}")
        return ":".join(parts)

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


    async def invalidate(self, pattern: str = "films:list*") -> None:
        """
        Invalidates all film list cache entries in Redis matching pattern.
        """
        if self.redis_client is None:
            return

        try:
            keys = await self.redis_client.keys(pattern)
            if keys:
                await self.redis_client.delete(*keys)
                logger.info(f"Invalidated {len(keys)} film-list cache entries in Redis (pattern: '{pattern}')")
        except redis.RedisError as e:
            logger.warning(f"Failed to invalidate film cache in Redis: {e}")
