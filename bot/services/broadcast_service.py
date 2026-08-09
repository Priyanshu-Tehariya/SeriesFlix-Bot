from __future__ import annotations

import asyncio
import structlog
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError, TelegramBadRequest
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.base import AsyncSessionFactory
from bot.database.repositories.user_repo import UserRepository

logger = structlog.get_logger(__name__)

class BroadcastService:
    @staticmethod
    async def run_broadcast(bot: Bot, admin_chat_id: int, broadcast_msg: Message, status_msg: Message, cleanup_ids: list[int] = None) -> None:
        """
        Background engine to send a broadcast message to all users.
        """
        # 1. Fetch all registered user IDs from PostgreSQL
        async with AsyncSessionFactory() as session:
            user_repo = UserRepository(session)
            user_ids = await user_repo.get_all_user_ids()

        total = len(user_ids)
        if total == 0:
            await bot.send_message(chat_id=admin_chat_id, text="No users found to broadcast.")
            return

        if not cleanup_ids:
            cleanup_ids = []

        sent = 0
        failed = 0
        
        # 3. Loop through user IDs using copy_to with rate limiting
        for i, user_id in enumerate(user_ids, 1):
            try:
                await broadcast_msg.copy_to(chat_id=user_id)
                sent += 1
            except (TelegramForbiddenError, TelegramBadRequest) as e:
                # User blocked the bot or deleted account -> mark inactive in DB
                failed += 1
                from sqlalchemy import update
                from bot.database.models.user import User
                await session.execute(
                    update(User).where(User.user_id == user_id).values(is_banned=True, ban_reason="bot_blocked")
                )
                await session.commit()
                logger.warning("broadcast_blocked_or_deleted", user_id=user_id, error=str(e))
            except TelegramAPIError as e:
                failed += 1
                logger.warning("broadcast_api_error", user_id=user_id, error=str(e))
            except Exception as e:
                failed += 1
                logger.exception("broadcast_unknown_error", user_id=user_id, error=str(e))

            # Update live progress card every 20 users or at the end
            if i % 20 == 0 or i == total:
                percentage = round((i / total) * 100, 1)
                update_text = (
                    "📢 *Broadcast Progress*\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"👥 *Total Targets:* {total}\n"
                    f"✅ *Delivered:* {sent}\n"
                    f"🚫 *Blocked/Failed:* {failed}\n"
                    f"📊 *Progress:* {percentage}%"
                )
                try:
                    await status_msg.edit_text(text=update_text, parse_mode="Markdown")
                except TelegramBadRequest:
                    # Message is not modified
                    pass
                except Exception as e:
                    logger.warning("broadcast_status_update_failed", error=str(e))

            await asyncio.sleep(0.05)

        # 1. Edit status_msg in-place into the final summary card FIRST
        final_card = (
            f"📢 *Broadcast Complete*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👥 *Total Targets:* {total}\n"
            f"✅ *Delivered:* {sent}\n"
            f"🚫 *Blocked/Failed:* {failed}\n"
            f"📊 *Progress:* 100.0%"
        )

        try:
            await status_msg.edit_text(final_card, parse_mode="Markdown")
        except Exception as e:
            logger.warning(f"Failed to edit status message: {e}")

        # 2. Add a tiny pause to allow Telegram state to synchronize
        await asyncio.sleep(0.5)

        # 3. Explicitly delete each setup message ID individually
        for msg_id in cleanup_ids:
            try:
                await bot.delete_message(chat_id=admin_chat_id, message_id=msg_id)
            except Exception as e:
                logger.warning(
                    f"Failed to delete setup message {msg_id} in chat {admin_chat_id}: {e}"
                )
