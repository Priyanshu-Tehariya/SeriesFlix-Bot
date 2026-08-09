from aiogram.filters import Filter
from aiogram.types import CallbackQuery, Message
from bot.config import settings

class IsAdmin(Filter):

  async def __call__(self, event: Message | CallbackQuery) -> bool:
    user_id = event.from_user.id
    return user_id in settings.ADMIN_IDS
