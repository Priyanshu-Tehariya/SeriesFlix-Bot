from __future__ import annotations

from typing import Any, Generic, Sequence, Type, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Generic async CRUD mixin. All specific repos inherit from this."""

    model: Type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, pk: Any) -> ModelT | None:
        return await self.session.get(self.model, pk)

    async def get_all(self) -> Sequence[ModelT]:
        result = await self.session.execute(select(self.model))
        return result.scalars().all()

    async def add(self, instance: ModelT) -> ModelT:
        self.session.add(instance)
        await self.session.flush()
        return instance

    async def delete(self, instance: ModelT) -> None:
        await self.session.delete(instance)
        await self.session.flush()

    async def refresh(self, instance: ModelT) -> ModelT:
        await self.session.refresh(instance)
        return instance
