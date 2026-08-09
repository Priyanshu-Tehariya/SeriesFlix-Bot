from aiogram.filters import Filter
from aiogram.types import CallbackQuery, Message
from bot.config import settings


class IsAdmin(Filter):

  async def __call__(self, event: Message | CallbackQuery) -> bool:
    return event.from_user.id in settings.ADMIN_IDS
