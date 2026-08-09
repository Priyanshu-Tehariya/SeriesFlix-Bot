from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from bot.database.base import AsyncSessionFactory


class DbSessionMiddleware(BaseMiddleware):
    """
    Injects an AsyncSession into the handler data dict under the key "session".
    Commits on success, rolls back on exception.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with AsyncSessionFactory() as session:
            data["session"] = session
            try:
                result = await handler(event, data)
                await session.commit()
                return result
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
