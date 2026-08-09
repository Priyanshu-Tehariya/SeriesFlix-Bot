from __future__ import annotations

from aiogram.filters import BaseFilter
from aiogram.types import Message

from bot.config import settings


class IsIndexChannel(BaseFilter):
    """True if the message originates from the configured index channel."""

    async def __call__(self, message: Message) -> bool:
        return message.chat.id == settings.INDEX_CHANNEL_ID
