from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from bot.database.repositories.user_repo import UserRepository


class UserRegistrarMiddleware(BaseMiddleware):
    """
    Upserts a User row on every incoming update from a real user.
    Must run AFTER DbSessionMiddleware (depends on data["session"]).
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        from_user = getattr(event, "from_user", None)
        session = data.get("session")

        if from_user and session:
            user_repo = UserRepository(session)
            user = await user_repo.upsert(
                user_id=from_user.id,
                full_name=from_user.full_name,
                username=from_user.username,
            )
            data["user"] = user

        return await handler(event, data)
