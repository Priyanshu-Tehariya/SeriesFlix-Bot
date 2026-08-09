from __future__ import annotations

import redis.asyncio as aioredis
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage

from bot.config import settings

# ---------------------------------------------------------------------------
# Telegram Bot & Dispatcher singletons
# ---------------------------------------------------------------------------

bot = Bot(
    token=settings.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)

redis_client: aioredis.Redis = aioredis.from_url(
    settings.REDIS_URL,
    encoding="utf-8",
    decode_responses=True,
)

# dp and storage moved to main.py for async initialization
