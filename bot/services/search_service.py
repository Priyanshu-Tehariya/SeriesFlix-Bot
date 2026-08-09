from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models.search_log import SearchLog
from bot.database.repositories.series_repo import SeriesRepository
from bot.services.cache_service import CacheService
from bot.utils.text import normalize_query
from bot.services.tmdb_service import get_poster_url, POSTER_BROKEN_SENTINEL

logger = structlog.get_logger(__name__)


class SearchService:
    """
    Query normalization + cache-aside search.

    Flow:
      1. Normalize user input.
      2. Check Redis cache (key: search:{normalized_query}).
      3. On miss: query Postgres via SeriesRepository.search_by_title().
      4. Repopulate cache with TTL_SEARCH.
      5. Log query to search_logs table.
    """

    def __init__(
        self,
        session: AsyncSession,
        cache: CacheService,
    ) -> None:
        self._session = session
        self._cache = cache
        self._series_repo = SeriesRepository(session)

    async def search(self, raw_query: str, user_id: int) -> list[dict]:
        """
        Returns a list of series dicts [{"id", "title", "poster_url", "rating", "summary"}].
        """
        normalized = normalize_query(raw_query)
        cache_key = CacheService.search_key(normalized)

        cached = await self._cache.get_json(cache_key)
        if cached is not None:
            # Bypass cache ONLY if poster_url is missing/empty AND not the __broken__ sentinel
            if any(
                not item.get("poster_url") and item.get("poster_url") != POSTER_BROKEN_SENTINEL
                for item in cached
            ):
                logger.info("Cached search results missing poster_url. Bypassing cache to fetch fresh poster from TMDB.")
                cached = None
            else:
                logger.debug("cache_hit", key=cache_key, user_id=user_id)
                await self._log_search(user_id, raw_query, len(cached))
                return cached  # type: ignore[return-value]

        logger.debug("cache_miss", key=cache_key, user_id=user_id)
        series_list = await self._series_repo.search_by_title(normalized, limit=10)

        from bot.services.tmdb_service import TMDBClient
        db_updated = False
        for s in series_list:
            # Skip TMDB re-fetch for series already marked as broken
            if not s.poster_url and s.poster_url != POSTER_BROKEN_SENTINEL:
                tmdb_data = await TMDBClient.search_series(s.title)
                if tmdb_data and tmdb_data.get("poster_url"):
                    s.poster_url = tmdb_data.get("poster_url")
                    db_updated = True
                    
        if db_updated:
            await self._session.commit()

        results = [
            {
                "id": s.id,
                "title": s.title,
                "poster_url": get_poster_url(s.poster_url) if s.poster_url != POSTER_BROKEN_SENTINEL else POSTER_BROKEN_SENTINEL,
                "rating": s.rating,
                "summary": s.summary,
            }
            for s in series_list
        ]

        if results:
            await self._cache.set_json(cache_key, results, CacheService.TTL_SEARCH)
        
        await self._log_search(user_id, raw_query, len(results))
        return results

    async def _log_search(self, user_id: int, query_text: str, results_count: int) -> None:
        log = SearchLog(
            user_id=user_id,
            query_text=query_text[:512],
            results_count=results_count,
        )
        self._session.add(log)
