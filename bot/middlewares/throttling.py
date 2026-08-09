from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from redis.asyncio import Redis
import structlog

logger = structlog.get_logger(__name__)


class ThrottlingMiddleware(BaseMiddleware):

  def __init__(self, redis: Redis, rate_limit_seconds: float = 1.0) -> None:
    self.redis = redis
    self.rate_limit_seconds = rate_limit_seconds

  async def __call__(
      self,
      handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
      event: TelegramObject,
      data: Dict[str, Any],
  ) -> Any:
    user_id = None
    if isinstance(event, (Message, CallbackQuery)) and event.from_user:
      user_id = event.from_user.id

    if user_id:
      key = f"rate_limit:{user_id}"
      is_throttled = await self.redis.get(key)

      if is_throttled:
        if isinstance(event, Message):
          await event.answer("⚠️ Please wait a moment before searching again.")
        elif isinstance(event, CallbackQuery):
          await event.answer("⚠️ Slow down!", show_alert=False)
        return

      await self.redis.set(
          key, "1", px=int(self.rate_limit_seconds * 1000)
      )

    return await handler(event, data)
