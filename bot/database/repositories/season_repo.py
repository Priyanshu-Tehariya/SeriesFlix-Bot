from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models.season import Season
from bot.database.repositories.base_repo import BaseRepository


class SeasonRepository(BaseRepository[Season]):
    model = Season

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_id(self, season_id: int) -> Season | None:
        return await self.session.get(Season, season_id)

    async def get_by_series(self, series_id: int) -> list[Season]:
        result = await self.session.execute(
            select(Season)
            .where(Season.series_id == series_id)
            .order_by(Season.season_number)
        )
        return list(result.scalars().all())

    async def get_or_create(self, series_id: int, season_number: int) -> tuple[Season, bool]:
        """Returns (season, created). Safe to call idempotently."""
        result = await self.session.execute(
            select(Season).where(
                Season.series_id == series_id,
                Season.season_number == season_number,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            return existing, False
        season = Season(series_id=series_id, season_number=season_number)
        self.session.add(season)
        await self.session.flush()
        return season, True
