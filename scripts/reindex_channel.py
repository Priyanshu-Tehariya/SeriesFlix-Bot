import asyncio
import logging
import argparse
import sys
from pathlib import Path

# Add project root to sys.path so we can run from anywhere
sys.path.append(str(Path(__file__).parent.parent))

from aiogram import Bot
from aiogram.types import Message
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from bot.config import settings
from bot.database.base import AsyncSessionFactory
from bot.loader import redis_client, bot
from bot.services.cache_service import CacheService
from bot.services.indexing_service import IndexingService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def reindex_channel(start_id: int, max_id: int, delay: float = 1.0):
    cache = CacheService(redis_client)
    
    success_count = 0
    skip_count = 0
    total_processed = 0
    total_to_process = max_id - start_id + 1
    
    logger.info(f"Starting re-indexing from message ID {start_id} to {max_id}")
    
    async with AsyncSessionFactory() as session:
        indexing_service = IndexingService(session, cache)
        
        for msg_id in range(start_id, max_id + 1):
            total_processed += 1
            if total_processed % 25 == 0:
                logger.info(f"Progress: {total_processed}/{total_to_process} messages scanned...")
                
            try:
                # Forward the message to the log channel (acting as a temporary dump)
                forwarded_msg = await bot.forward_message(
                    chat_id=settings.LOG_CHANNEL_ID,
                    from_chat_id=settings.INDEX_CHANNEL_ID,
                    message_id=msg_id,
                    disable_notification=True
                )
                
                try:
                    # Extract media and filename
                    media = forwarded_msg.document or forwarded_msg.video
                    
                    if not media:
                        logger.debug(f"Message {msg_id} contains no document/video.")
                        skip_count += 1
                    else:
                        raw_filename = (
                            forwarded_msg.caption or getattr(media, 'file_name', None) or "Unknown_File"
                        ).strip()
                        
                        file_id = media.file_id
                        file_unique_id = media.file_unique_id
                        file_size = media.file_size or 0
                        
                        if raw_filename != "Unknown_File":
                            created, ep_id = await indexing_service.ingest(
                                filename=raw_filename,
                                file_id=file_id,
                                file_unique_id=file_unique_id,
                                file_size=file_size,
                            )
                            
                            from bot.utils.regex_engine import FilenameParser
                            parsed = FilenameParser.parse(raw_filename)
                            ep_label = f"{parsed.start_ep}-{parsed.end_ep}" if (parsed.start_ep is not None and parsed.end_ep is not None and parsed.start_ep != parsed.end_ep) else str(parsed.episode or 0)
                            
                            if created:
                                logger.info(f"Successfully indexed msg {msg_id} (S{parsed.season or 0} E{ep_label}): {raw_filename[:40]}...")
                                success_count += 1
                            else:
                                logger.debug(f"Skipped/Duplicate msg {msg_id} (S{parsed.season or 0} E{ep_label}): {raw_filename[:40]}...")
                                skip_count += 1
                        else:
                            skip_count += 1
                finally:
                    # Delete the temporarily forwarded message to clean up the log channel
                    await bot.delete_message(
                        chat_id=settings.LOG_CHANNEL_ID,
                        message_id=forwarded_msg.message_id
                    )
                
            except TelegramBadRequest as e:
                # E.g. "message to forward not found" (deleted message) or "message can't be forwarded"
                logger.debug(f"Message {msg_id} failed/skipped: {e}")
                skip_count += 1
                continue
            except TelegramForbiddenError as e:
                logger.error(f"Bot lacks permissions to copy from index channel or post to log channel: {e}")
                break
            except Exception as e:
                logger.error(f"Unexpected error processing message {msg_id}: {e}")
                skip_count += 1
                continue
            
            # Rate limiting delay
            await asyncio.sleep(delay)
            
    logger.info(f"Re-indexing complete. Successfully indexed: {success_count}, Skipped/Failed: {skip_count}")

def main():
    parser = argparse.ArgumentParser(description="Re-index historical messages from the Telegram Index Channel.")
    parser.add_argument("--start", type=int, required=True, help="The message ID to start indexing from.")
    parser.add_argument("--end", type=int, required=True, help="The message ID to end indexing at.")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay in seconds between forwarding messages (default: 1.0 to avoid flood waits).")
    
    args = parser.parse_args()
    
    asyncio.run(reindex_channel(start_id=args.start, max_id=args.end, delay=args.delay))

if __name__ == "__main__":
    main()
