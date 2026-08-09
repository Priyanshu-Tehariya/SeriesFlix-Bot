from __future__ import annotations

import asyncio
import logging

import structlog
from aiogram import Dispatcher

logger = structlog.get_logger(__name__)

from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import Redis

from bot.config import settings
from bot.handlers import register_all_routers
from bot.loader import bot, redis_client
from bot.middlewares.ban_check import BanCheckMiddleware
from bot.middlewares.db_session import DbSessionMiddleware
from bot.middlewares.logging_middleware import LoggingMiddleware
from bot.middlewares.throttling import ThrottlingMiddleware
from bot.middlewares.user_registrar import UserRegistrarMiddleware
from bot.middlewares.force_sub import ForceSubMiddleware

# ---------------------------------------------------------------------------
# Structlog configuration — JSON to stdout
# ---------------------------------------------------------------------------

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.BoundLogger,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL, logging.INFO))


def setup_middlewares(dp: Dispatcher) -> None:
    """
    Register middlewares in the correct order:
    Logging → DbSession → UserRegistrar → BanCheck → Throttling
    """
    # Middlewares that need a user context
    for observer in (dp.message, dp.callback_query):
        observer.outer_middleware(LoggingMiddleware())
        observer.outer_middleware(DbSessionMiddleware())
        observer.outer_middleware(UserRegistrarMiddleware())
        observer.outer_middleware(BanCheckMiddleware())
        observer.outer_middleware(ForceSubMiddleware())
        observer.outer_middleware(ThrottlingMiddleware(redis=redis_client, rate_limit_seconds=1.0))

    # Middlewares for channel posts (no user context needed)
    dp.channel_post.outer_middleware(LoggingMiddleware())
    dp.channel_post.outer_middleware(DbSessionMiddleware())

    # Inject redis client into all handlers
    dp["redis"] = redis_client


async def get_storage():
    if not getattr(settings, "REDIS_URL", None):
        logger.info("No REDIS_URL configured. Using MemoryStorage.")
        return MemoryStorage()

    try:
        redis = Redis.from_url(settings.REDIS_URL)
        # Test connection before assigning to dispatcher
        await redis.ping()
        logger.info("Connected to Redis FSM Storage.")
        return RedisStorage(redis=redis)
    except Exception as e:
        logger.warning(
            f"Redis connection failed ({e}). Falling back to MemoryStorage for local run."
        )
        return MemoryStorage()


async def main() -> None:
    storage = await get_storage()
    dp = Dispatcher(storage=storage)
    
    setup_middlewares(dp)
    register_all_routers(dp)

    import structlog
    log = structlog.get_logger(__name__)
    log.info("bot_starting", bot_id=bot.id if hasattr(bot, "id") else "unknown")

    # One-time startup: create all missing DB tables (e.g. tracked_shows)
    from bot.database.base import Base, engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # One-time startup: purge known dead poster paths from Postgres
    from bot.database.base import AsyncSessionFactory
    from sqlalchemy import text
    async with AsyncSessionFactory() as cleanup_session:
        try:
            result = await cleanup_session.execute(
                text("UPDATE series SET poster_url = NULL WHERE poster_url = '__broken__' OR poster_url LIKE 'http%';")
            )
            await cleanup_session.commit()
            if result.rowcount:
                log.info("startup_cleanup", purged_stale_posters=result.rowcount)
        except Exception as e:
            log.warning(f"Startup poster cleanup failed (non-fatal): {e}")

    # Flush stale search/meta cache keys that may reference dead poster URLs
    try:
        await redis_client.flushdb()
        log.info("startup_cache_flush")
    except Exception as e:
        log.warning(f"Redis flush on startup failed (non-fatal): {e}")

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()
        await redis_client.aclose()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("\n[info] Bot stopped gracefully.")
