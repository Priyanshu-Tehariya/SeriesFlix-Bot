from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models.episode import QualityEnum
from bot.database.repositories.episode_repo import EpisodeRepository
from bot.database.repositories.season_repo import SeasonRepository
from bot.database.repositories.series_repo import SeriesRepository
from bot.services.cache_service import CacheService
from bot.services.tmdb_service import get_poster_url, POSTER_BROKEN_SENTINEL

logger = structlog.get_logger(__name__)


class NavigationService:
    """
    Builds the view payloads used by the navigation handlers.

    Each method returns a plain dict/list that handlers serialise into
    keyboard + caption text — keeping handler code thin.
    """

    def __init__(self, session: AsyncSession, cache: CacheService) -> None:
        self._session = session
        self._cache = cache
        self._series_repo = SeriesRepository(session)
        self._season_repo = SeasonRepository(session)
        self._episode_repo = EpisodeRepository(session)

    # ------------------------------------------------------------------
    # Season picker payload
    # ------------------------------------------------------------------

    async def get_seasons(self, series_id: int) -> list[dict]:
        """
        Returns [{"id", "season_number"}, ...] ordered by season_number.
        Cache key: series:{series_id}:seasons
        """
        cache_key = CacheService.seasons_key(series_id)
        cached = await self._cache.get_json(cache_key)
        if cached is not None:
            return cached  # type: ignore[return-value]

        seasons = await self._season_repo.get_by_series(series_id)
        payload = [{"id": s.id, "season_number": s.season_number} for s in seasons]
        
        if payload:
            await self._cache.set_json(cache_key, payload, CacheService.TTL_SEASONS)
            
        return payload

    # ------------------------------------------------------------------
    # Quality picker payload
    # ------------------------------------------------------------------

    async def get_qualities(self, season_id: int) -> list[str]:
        """
        Returns distinct quality strings available for a season.
        Incorporates ZIP/complete-season detection (episode_number == 0).
        """
        # Qualities are embedded in the episodes cache so we compute from DB directly
        return await self._episode_repo.get_qualities_for_season(season_id)

    # ------------------------------------------------------------------
    # Episode grid payload
    # ------------------------------------------------------------------

    async def get_episodes(self, season_id: int, quality: str) -> list[dict]:
        """
        Returns [{"id", "episode_number", "file_size", "language"}, ...].
        Cache key: season:{season_id}:episodes:{quality}
        """
        cache_key = CacheService.episodes_key(season_id, quality)
        cached = await self._cache.get_json(cache_key)
        if cached is not None:
            return cached  # type: ignore[return-value]

        try:
            quality_enum = QualityEnum(quality)
        except ValueError:
            quality_enum = QualityEnum.SOURCE_UNKNOWN

        episodes = await self._episode_repo.get_by_season_and_quality(season_id, quality_enum)
        payload = [
            {
                "id": ep.id,
                "episode_number": ep.episode_number,
                "file_size": ep.file_size,
                "language": ep.language,
            }
            for ep in episodes
        ]
        
        if payload:
            await self._cache.set_json(cache_key, payload, CacheService.TTL_EPISODES)
            
        return payload

    # ------------------------------------------------------------------
    # Episode delivery payload
    # ------------------------------------------------------------------

    async def get_episode_for_delivery(self, episode_id: int) -> dict | None:
        """Returns full episode dict for file delivery, or None if not found/inactive."""
        ep = await self._episode_repo.get_by_id(episode_id)
        if ep is None or not ep.is_active:
            return None
        return {
            "id": ep.id,
            "file_id": ep.file_id,
            "file_size": ep.file_size,
            "quality": ep.quality.value,
            "language": ep.language,
            "episode_number": ep.episode_number,
            "download_count": ep.download_count,
            "raw_filename": ep.raw_filename,
        }

    async def increment_download(self, episode_id: int) -> None:
        await self._episode_repo.increment_download_count(episode_id)

    # ------------------------------------------------------------------
    # Series meta (for caption rendering)
    # ------------------------------------------------------------------

    async def get_series_meta(self, series_id: int) -> dict | None:
        cache_key = CacheService.meta_key(series_id)
        cached = await self._cache.get_json(cache_key)
        if cached is not None:
            # Bypass cache ONLY if poster_url is missing/empty AND not the __broken__ sentinel
            if not cached.get("poster_url") and cached.get("poster_url") != POSTER_BROKEN_SENTINEL:
                logger.info("Cached series missing poster_url. Bypassing cache to fetch fresh poster from TMDB.")
                cached = None
            else:
                return cached  # type: ignore[return-value]

        series = await self._series_repo.get_by_id(series_id)
        if series is None:
            return None
            
        payload = {
            "id": series.id,
            "title": series.title,
            "poster_url": get_poster_url(series.poster_url) if series.poster_url != POSTER_BROKEN_SENTINEL else POSTER_BROKEN_SENTINEL,
            "rating": series.rating if series.rating else "",
            "summary": series.summary if series.summary else "",
            "year": "",
            "genres": "",
        }

        # Skip TMDB enrichment for series with broken poster sentinel
        if series.poster_url != POSTER_BROKEN_SENTINEL:
            from bot.services.tmdb_service import TMDBClient
            tmdb_data = await TMDBClient.search_series(series.title)
            
            if tmdb_data:
                payload["title"] = tmdb_data.get("name") or payload["title"]
                payload["poster_url"] = get_poster_url(tmdb_data.get("poster_url")) or payload["poster_url"]
                payload["summary"] = tmdb_data.get("summary") or payload["summary"]
                payload["rating"] = tmdb_data.get("rating") or payload["rating"]
                payload["year"] = tmdb_data.get("year", "")
                payload["genres"] = tmdb_data.get("genres", "")
                
                # Persist back to DB if missing
                if tmdb_data.get("poster_url") and not series.poster_url:
                    series.poster_url = tmdb_data.get("poster_url")
                    await self._session.commit()

        await self._cache.set_json(cache_key, payload, CacheService.TTL_META)
        return payload
