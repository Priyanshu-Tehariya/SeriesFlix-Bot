from __future__ import annotations

import json
from typing import Any

from redis.asyncio import Redis


class CacheService:
    """
    Thin async Redis wrapper providing JSON get/set/delete and prefix invalidation.

    Key naming convention (from ARCHITECTURE.md §5.6):
      search:{normalized_query}           TTL 10 min
      series:{series_id}:seasons          TTL 30 min
      season:{season_id}:episodes:{quality} TTL 30 min
      series:{series_id}:meta             TTL 1 hour
    """

    TTL_SEARCH = 600       # 10 minutes
    TTL_SEASONS = 1800     # 30 minutes
    TTL_EPISODES = 1800    # 30 minutes
    TTL_META = 3600        # 1 hour

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def get_json(self, key: str) -> dict | list | None:
        raw = await self._redis.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    async def set_json(self, key: str, value: dict | list, ttl: int) -> None:
        await self._redis.setex(key, ttl, json.dumps(value, default=str))

    async def delete(self, key: str) -> None:
        await self._redis.delete(key)

    async def invalidate_prefix(self, prefix: str) -> None:
        """SCAN + UNLINK all keys matching prefix* — used after indexing writes."""
        cursor = 0
        while True:
            cursor, keys = await self._redis.scan(cursor, match=f"{prefix}*", count=100)
            if keys:
                await self._redis.unlink(*keys)
            if cursor == 0:
                break

    # --- Convenience key builders ---

    @staticmethod
    def search_key(normalized_query: str) -> str:
        return f"search:{normalized_query}"

    @staticmethod
    def seasons_key(series_id: int) -> str:
        return f"series:{series_id}:seasons"

    @staticmethod
    def episodes_key(season_id: int, quality: str) -> str:
        return f"season:{season_id}:episodes:{quality}"

    @staticmethod
    def meta_key(series_id: int) -> str:
        return f"series:{series_id}:meta"
