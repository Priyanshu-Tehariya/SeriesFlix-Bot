from __future__ import annotations

import hashlib

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models.episode import QualityEnum
from bot.database.repositories.episode_repo import EpisodeRepository
from bot.database.repositories.season_repo import SeasonRepository
from bot.database.repositories.series_repo import SeriesRepository
from bot.services.cache_service import CacheService
from bot.utils.regex_engine import FilenameParser

logger = structlog.get_logger(__name__)


class IndexingService:
    """
    Channel post ingestion pipeline.

    Ingest flow (idempotent — safe to re-run against same file):
      1. Extract file_id / file_unique_id / file_size from the Telegram message.
      2. Compute file_hash = sha256(file_unique_id).
      3. If file_hash already exists in DB → early-exit (idempotency check).
      4. Parse the filename with FilenameParser.
      5. Upsert Series → Season → Episode in a single transaction.
      6. Invalidate relevant Redis cache keys.
    """

    def __init__(self, session: AsyncSession, cache: CacheService) -> None:
        self._session = session
        self._cache = cache
        self._series_repo = SeriesRepository(session)
        self._season_repo = SeasonRepository(session)
        self._episode_repo = EpisodeRepository(session)

    @staticmethod
    def _compute_file_hash(file_unique_id: str) -> str:
        return hashlib.sha256(file_unique_id.encode()).hexdigest()

    async def ingest(
        self,
        filename: str,
        file_id: str,
        file_unique_id: str,
        file_size: int,
    ) -> tuple[bool, int | None]:
        """
        Parse and store a file from the index channel.

        Returns (created, episode_id) where created is True if a new episode was created, False if already indexed or unparseable.
        """
        file_hash = self._compute_file_hash(file_unique_id)

        # Idempotency check — exit early if we've already seen this file
        existing = await self._episode_repo.get_by_file_hash(file_hash)
        if existing is not None:
            logger.info("indexing_skipped_duplicate", file_hash=file_hash, filename=filename)
            return False, existing.id

        parsed = FilenameParser.parse(filename)

        if parsed.series_name is None or parsed.season is None:
            logger.warning(
                "indexing_parse_failed",
                filename=filename,
                series_name=parsed.series_name,
                season=parsed.season,
            )
            return False, None

        # --- Map quality string to QualityEnum ---
        quality_map: dict[str, QualityEnum] = {
            "480p": QualityEnum.Q480P,
            "720p": QualityEnum.Q720P,
            "1080p": QualityEnum.Q1080P,
            "4K": QualityEnum.Q4K,
        }
        quality_enum = quality_map.get(parsed.quality, QualityEnum.SOURCE_UNKNOWN)
        language = parsed.language_display

        # --- Upsert Series ---
        from bot.utils.text import normalize_query
        normalized = normalize_query(parsed.series_name)
        series, series_created = await self._series_repo.upsert_by_normalized_title(
            title=parsed.series_name,
            normalized_title=normalized,
        )

        # --- Upsert Season ---
        season, _ = await self._season_repo.get_or_create(
            series_id=series.id,
            season_number=parsed.season,
        )

        # --- Upsert Episode ---
        episode_number = parsed.episode if parsed.episode is not None else 0
        episode, ep_created = await self._episode_repo.upsert_by_file_hash(
            file_hash=file_hash,
            season_id=season.id,
            episode_number=episode_number,
            file_id=file_id,
            file_unique_id=file_unique_id,
            file_size=file_size,
            quality=quality_enum,
            language=language,
            raw_filename=filename,
        )

        # Commit transaction to ensure data is saved
        await self._session.commit()

        # --- Invalidate cache ---
        if series_created:
            # New series → search results may now include it
            await self._cache.invalidate_prefix("search:")
        await self._cache.invalidate_prefix(f"series:{series.id}:")
        await self._cache.invalidate_prefix(f"season:{season.id}:")

        logger.info(
            "indexing_success",
            filename=filename,
            series=series.title,
            season=parsed.season,
            episode=episode_number,
            quality=quality_enum.value,
            created=ep_created,
        )
        return ep_created, episode.id
