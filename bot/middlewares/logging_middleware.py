from __future__ import annotations

import time
from typing import Any, Awaitable, Callable

import structlog
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

logger = structlog.get_logger(__name__)


class LoggingMiddleware(BaseMiddleware):
    """
    Structured request/response logging using structlog.
    Logs update type, user_id, chat_id, and handler execution time.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        from_user = getattr(event, "from_user", None)
        chat = getattr(event, "chat", None)

        log = logger.bind(
            update_type=type(event).__name__,
            user_id=from_user.id if from_user else None,
            chat_id=chat.id if chat else None,
        )

        start = time.monotonic()
        try:
            result = await handler(event, data)
            elapsed_ms = round((time.monotonic() - start) * 1000, 2)
            log.debug("handler_ok", elapsed_ms=elapsed_ms)
            return result
        except Exception as exc:
            elapsed_ms = round((time.monotonic() - start) * 1000, 2)
            log.exception("handler_error", elapsed_ms=elapsed_ms, error=str(exc))
            raise
