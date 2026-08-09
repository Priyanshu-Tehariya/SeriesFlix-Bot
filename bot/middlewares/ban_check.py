from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from bot.database.repositories.user_repo import UserRepository


class BanCheckMiddleware(BaseMiddleware):
    """
    Silently drops updates from users whose User.is_banned == True.
    Reads from the session already injected by DbSessionMiddleware.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        # Only check messages and callback queries from real users
        from_user = getattr(event, "from_user", None)
        if from_user is None:
            return await handler(event, data)

        session = data.get("session")
        if session is None:
            return await handler(event, data)

        user_repo = UserRepository(session)
        user = await user_repo.get_by_id(from_user.id)

        if user and user.is_banned:

            if isinstance(event, Message):
                reason_text = f"\nReason: {user.ban_reason}" if user.ban_reason else ""
                await event.answer(f"🚫 You have been banned from using this bot.{reason_text}")
            return None  # Drop the update

        return await handler(event, data)
