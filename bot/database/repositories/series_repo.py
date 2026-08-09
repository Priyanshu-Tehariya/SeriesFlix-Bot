from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models.episode import Episode
from bot.database.models.season import Season
from bot.database.models.series import Series
from bot.database.repositories.base_repo import BaseRepository
from bot.utils.text import normalize_query


class SeriesRepository(BaseRepository[Series]):
    model = Series

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_id(self, series_id: int) -> Series | None:
        return await self.session.get(Series, series_id)

    async def get_by_normalized_title(self, normalized_title: str) -> Series | None:
        result = await self.session.execute(
            select(Series).where(Series.normalized_title == normalized_title)
        )
        return result.scalar_one_or_none()

    async def search_by_title(self, query: str, limit: int = 10) -> list[Series]:
        """ILIKE prefix search across normalized_title, or exact lowercased title match."""
        from bot.database.models.season import Season
        from bot.database.models.episode import Episode
        from sqlalchemy import or_

        result = await self.session.execute(
            select(Series)
            .join(Season)
            .join(Episode)
            .where(
                or_(
                    func.lower(Series.title) == query.lower(),
                    Series.normalized_title.ilike(f"%{query}%")
                )
            )
            .group_by(Series.id)
            .order_by(Series.title)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def upsert_by_normalized_title(
        self,
        title: str,
        normalized_title: str,
    ) -> tuple[Series, bool]:
        """Returns (series, created). Creates if not exists, returns existing otherwise."""
        stmt = pg_insert(Series).values(
            title=title,
            normalized_title=normalized_title,
        )
        
        # Use PostgreSQL ON CONFLICT DO UPDATE to handle race conditions
        stmt = stmt.on_conflict_do_update(
            index_elements=['normalized_title'],
            set_={'title': stmt.excluded.title}
        ).returning(Series)
        
        try:
            result = await self.session.execute(stmt)
            row = result.scalar_one_or_none()
            if row:
                # To be safe with cache invalidation, we can just say True
                # so the search cache is invalidated on upserts just in case.
                return row, True
            await self.session.flush()
        except IntegrityError:
            # Fallback if there's an extremely tight race or transaction failure
            await self.session.rollback()
            existing = await self.get_by_normalized_title(normalized_title)
            if existing:
                return existing, False
            raise  # If it still fails, re-raise

        # As a fallback if the returning clause fails for some reason
        existing = await self.get_by_normalized_title(normalized_title)
        if existing:
            return existing, False
        raise RuntimeError(f"Failed to upsert series {title}")

    async def get_total_series(self) -> int:
        result = await self.session.execute(select(func.count(Series.id)))
        return result.scalar_one()

    async def get_by_id_or_title(self, query: str | int) -> Series | None:
        """Resolve series by numeric ID or normalized-title substring match."""
        if isinstance(query, int) or (isinstance(query, str) and query.strip().isdigit()):
            return await self.get_by_id(int(query))
        
        normalized = normalize_query(str(query))
        results = await self.search_by_title(normalized, limit=1)
        return results[0] if results else None

    async def delete_by_id_or_title(self, query: str | int) -> "DeletionResult | None":
        """
        Resolve series by numeric ID (int or digit string) or by normalized-title
        substring match (first result). Returns a DeletionResult or None if not found.

        The caller (handler) is responsible for invalidating Redis cache after deletion
        so it can pass the CacheService without this repo needing to import it.
        """
        series: Series | None = None

        # --- Resolve ---
        if isinstance(query, int) or (isinstance(query, str) and query.strip().isdigit()):
            series = await self.get_by_id(int(query))
        else:
            normalized = normalize_query(str(query))
            results = await self.search_by_title(normalized, limit=1)
            series = results[0] if results else None

        if series is None:
            return None

        series_id = series.id
        series_title = series.title

        # --- Count episodes before cascade delete ---
        season_ids_result = await self.session.execute(
            select(Season.id).where(Season.series_id == series_id)
        )
        season_ids = [row[0] for row in season_ids_result.all()]

        episode_count = 0
        if season_ids:
            ep_count_result = await self.session.execute(
                select(func.count(Episode.id)).where(Episode.season_id.in_(season_ids))
            )
            episode_count = ep_count_result.scalar_one()

        # --- Delete (CASCADE handles seasons + episodes) ---
        await self.session.delete(series)
        await self.session.flush()

        return DeletionResult(
            series_id=series_id,
            series_title=series_title,
            deleted_episodes=episode_count,
        )


@dataclass
class DeletionResult:
    series_id: int
    series_title: str
    deleted_episodes: int
