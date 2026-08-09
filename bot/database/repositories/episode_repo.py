from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models.episode import Episode, QualityEnum
from bot.database.repositories.base_repo import BaseRepository


class EpisodeRepository(BaseRepository[Episode]):
    model = Episode

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_id(self, episode_id: int) -> Episode | None:
        return await self.session.get(Episode, episode_id)

    async def get_by_file_hash(self, file_hash: str) -> Episode | None:
        result = await self.session.execute(
            select(Episode).where(Episode.file_hash == file_hash)
        )
        return result.scalar_one_or_none()

    async def get_by_season_and_quality(
        self, season_id: int, quality: QualityEnum
    ) -> list[Episode]:
        result = await self.session.execute(
            select(Episode)
            .where(
                Episode.season_id == season_id,
                Episode.quality == quality,
                Episode.is_active.is_(True),
            )
            .order_by(Episode.episode_number)
        )
        return list(result.scalars().all())

    async def get_qualities_for_season(self, season_id: int) -> list[str]:
        """Distinct active quality values for a given season."""
        result = await self.session.execute(
            select(Episode.quality)
            .where(Episode.season_id == season_id, Episode.is_active.is_(True))
            .distinct()
        )
        return [row[0].value for row in result.all()]

    async def upsert_by_file_hash(
        self,
        file_hash: str,
        season_id: int,
        episode_number: int,
        file_id: str,
        file_unique_id: str,
        file_size: int,
        quality: QualityEnum,
        language: str,
        raw_filename: str,
    ) -> tuple[Episode, bool]:
        """Idempotent upsert. Returns (episode, created)."""
        existing = await self.get_by_file_hash(file_hash)
        if existing:
            # Update mutable fields (file_id can change after channel re-upload)
            existing.file_id = file_id
            existing.raw_filename = raw_filename
            return existing, False

        episode = Episode(
            file_hash=file_hash,
            season_id=season_id,
            episode_number=episode_number,
            file_id=file_id,
            file_unique_id=file_unique_id,
            file_size=file_size,
            quality=quality,
            language=language,
            raw_filename=raw_filename,
        )
        self.session.add(episode)
        await self.session.flush()
        return episode, True

    async def increment_download_count(self, episode_id: int) -> None:
        await self.session.execute(
            update(Episode)
            .where(Episode.id == episode_id)
            .values(download_count=Episode.download_count + 1)
        )

    async def delete_by_id(self, episode_id: int) -> tuple[int, int] | None:
        """Deletes the episode by id and returns (series_id, season_id) for cache invalidation."""
        from bot.database.models.season import Season
        from sqlalchemy.orm import joinedload
        
        result = await self.session.execute(
            select(Episode)
            .options(joinedload(Episode.season))
            .where(Episode.id == episode_id)
        )
        episode = result.scalar_one_or_none()
        if not episode:
            return None
            
        series_id = episode.season.series_id
        season_id = episode.season_id
        
        await self.session.delete(episode)
        await self.session.flush()

        # Orphan Cleanup
        # 1. Check if Season is empty
        season_eps = await self.session.execute(
            select(Episode.id).where(Episode.season_id == season_id).limit(1)
        )
        if not season_eps.first():
            season_obj = await self.session.get(Season, season_id)
            if season_obj:
                await self.session.delete(season_obj)
                await self.session.flush()

                # 2. Check if Series is empty
                series_seasons = await self.session.execute(
                    select(Season.id).where(Season.series_id == series_id).limit(1)
                )
                if not series_seasons.first():
                    from bot.database.models.series import Series
                    series_obj = await self.session.get(Series, series_id)
                    if series_obj:
                        await self.session.delete(series_obj)
                        await self.session.flush()

        return series_id, season_id

    async def delete_older_than(self, days: int) -> int:
        """Deletes all Episode rows created older than `days` days ago and returns count."""
        from datetime import datetime, timedelta, timezone
        from sqlalchemy import delete
        
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        result = await self.session.execute(
            delete(Episode).where(Episode.created_at < cutoff_date)
        )
        return result.rowcount
