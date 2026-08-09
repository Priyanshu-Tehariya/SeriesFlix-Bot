from __future__ import annotations

import asyncio
import structlog
from aiogram import Bot, F, Router
from aiogram.enums import ContentType
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.base import AsyncSessionFactory
from bot.filters.is_index_channel import IsIndexChannel
from bot.loader import redis_client
from bot.services.admin_log_service import AdminLogService
from bot.services.cache_service import CacheService
from bot.services.indexing_service import IndexingService
from bot.utils.regex_engine import FilenameParser
from bot.utils.text_formatters import format_file_size

logger = structlog.get_logger(__name__)

router = Router(name="channel_auto_index")
router.channel_post.filter(IsIndexChannel())

_batch_buffer: list[dict] = []
_batch_task: asyncio.Task | None = None


@router.channel_post(F.content_type.in_({ContentType.DOCUMENT, ContentType.VIDEO}))
async def auto_index(message: Message, session: AsyncSession) -> None:
    """
    Listens to document and video posts in the index channel and ingests them.
    """
    file = message.document or message.video
    if file is None:
        return

    raw_filename = (
        message.caption
        or (message.document.file_name if message.document else None)
        or (message.video.file_name if message.video else None)
        or "Unknown_File"
    ).strip()
    file_id = file.file_id
    file_unique_id = file.file_unique_id
    file_size = file.file_size or 0

    if raw_filename == "Unknown_File":
        logger.warning("auto_index_no_filename", file_unique_id=file_unique_id)
        return

    parsed = FilenameParser.parse(raw_filename)
    
    item = {
        "raw_filename": raw_filename,
        "file_id": file_id,
        "file_unique_id": file_unique_id,
        "file_size": file_size,
        "parsed": parsed,
    }
    
    _batch_buffer.append(item)
    
    global _batch_task
    if _batch_task is None and message.bot:
        _batch_task = asyncio.create_task(_process_batch(message.bot))


async def _process_batch(bot: Bot) -> None:
    """Debouncer task that waits, sorts the accumulated items, and indexes them sequentially."""
    global _batch_task
    
    await asyncio.sleep(2.5)
    
    # Snapshot and reset
    batch = list(_batch_buffer)
    _batch_buffer.clear()
    _batch_task = None
    
    if not batch:
        return
        
    # Sort by season and episode
    batch.sort(key=lambda item: (
        item["parsed"].season or 0,
        item["parsed"].episode or 0
    ))
    
    admin_log = AdminLogService(bot)
    
    # Process sequentially using a new isolated session
    async with AsyncSessionFactory() as session:
        cache = CacheService(redis_client)
        svc = IndexingService(session, cache)
        
        for item in batch:
            created, episode_id = await svc.ingest(
                filename=item["raw_filename"],
                file_id=item["file_id"],
                file_unique_id=item["file_unique_id"],
                file_size=item["file_size"],
            )
            
            if created:
                parsed = item["parsed"]
                await admin_log.log_indexing_success(
                    raw_filename=item["raw_filename"],
                    series_title=parsed.series_name or "Unknown",
                    season_num=parsed.season or 0,
                    episode_num=parsed.episode or 0,
                    quality=parsed.quality or "Unknown",
                    language=parsed.language_display or "Unknown",
                    formatted_size=format_file_size(item["file_size"]),
                    episode_id=episode_id or 0,
                )
                await asyncio.sleep(0.5)
