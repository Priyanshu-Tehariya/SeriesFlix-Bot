from __future__ import annotations

from aiogram.enums import ChatType
from aiogram.filters import BaseFilter
from aiogram.types import Message


class ChatTypeFilter(BaseFilter):
    """Filter by chat type(s). Usage: ChatTypeFilter(ChatType.PRIVATE)"""

    def __init__(self, *chat_types: ChatType) -> None:
        self.chat_types = set(chat_types)

    async def __call__(self, message: Message) -> bool:
        return message.chat.type in self.chat_types
