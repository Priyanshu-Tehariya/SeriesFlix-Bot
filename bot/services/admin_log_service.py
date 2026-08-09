from __future__ import annotations

import structlog
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.config import settings
from bot.keyboards.callback_factories import AdminDeleteFileCB

logger = structlog.get_logger(__name__)


class AdminLogService:
    """
    Sends structured log messages to the Admin/Log channel.

    All sends are fire-and-forget — failures are logged but not re-raised
    so the main bot flow is never blocked by admin channel issues.
    """

    def __init__(self, bot: Bot) -> None:
        self._bot = bot
        self._channel_id = settings.LOG_CHANNEL_ID

    async def _send(self, text: str, reply_markup: InlineKeyboardMarkup | None = None) -> None:
        try:
            await self._bot.send_message(
                chat_id=self._channel_id,
                text=text,
                parse_mode="HTML",
                reply_markup=reply_markup,
            )
        except TelegramBadRequest as e:
            logger.warning("admin_log_send_failed", error=str(e))
        except Exception as e:
            logger.error("admin_log_unexpected_error", error=str(e))

    async def log_search(self, user_id: int, full_name: str, query: str, result_count: int) -> None:
        text = (
            f"🔍 <b>Search</b>\n"
            f"User: <a href='tg://user?id={user_id}'>{full_name}</a>\n"
            f"Query: <b>{query}</b>\n"
            f"Results: <b>{result_count}</b>"
        )
        await self._send(text)

    async def log_ban(self, admin_id: int, target_user_id: int, reason: str | None) -> None:
        text = (
            f"🚫 <b>User Banned</b>\n"
            f"Admin: <a href='tg://user?id={admin_id}'>{admin_id}</a>\n"
            f"Target: <code>{target_user_id}</code>\n"
            f"Reason: {reason or 'No reason given'}"
        )
        await self._send(text)

    async def log_indexing_success(
        self,
        raw_filename: str,
        series_title: str,
        season_num: int,
        episode_num: int,
        quality: str,
        language: str,
        formatted_size: str,
        episode_id: int,
    ) -> None:
        from bot.utils.text_formatters import clean_language_display
        ep_label = "Complete" if episode_num == 0 else str(episode_num)
        text = (
            f"🍿 <b>New Content Indexed</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"📺 <b>Series:</b> {series_title}\n"
            f"🗓 <b>Season:</b> {season_num} | <b>Episode:</b> {ep_label}\n"
            f"🎥 <b>Quality:</b> <code>{quality}</code>\n"
            f"🌐 <b>Language:</b> <code>{clean_language_display(language)}</code>\n"
            f"💾 <b>Size:</b> {formatted_size}\n"
            f"📁 <b>Filename:</b> <code>{raw_filename}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"⚡️ <i>Status: Ready for streaming in Bot</i>"
        )
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🗑 Delete File",
                        callback_data=AdminDeleteFileCB(episode_id=episode_id).pack()
                    )
                ]
            ]
        )
        await self._send(text, reply_markup=kb)

    async def log_deletion(
        self,
        admin_id: int,
        series_title: str,
        series_id: int,
        deleted_episodes: int,
    ) -> None:
        """Log a /delete action to LOG_CHANNEL_ID."""
        text = (
            f"🗑 <b>Series Deleted</b>\n"
            f"Admin: <a href='tg://user?id={admin_id}'>{admin_id}</a>\n"
            f"Series: <b>{series_title}</b> (ID: <code>{series_id}</code>)\n"
            f"Deleted episodes: <b>{deleted_episodes}</b>"
        )
        await self._send(text)
    async def log_bulk_deletion(
        self,
        admin_id: int,
        days: int,
        deleted_count: int,
    ) -> None:
        """Log a /prune_older_than action to LOG_CHANNEL_ID."""
        text = (
            f"🧹 <b>Bulk Prune Executed</b>\n"
            f"Admin: <a href='tg://user?id={admin_id}'>{admin_id}</a>\n"
            f"Threshold: <b>Older than {days} days</b>\n"
            f"Files removed: <b>{deleted_count}</b>"
        )
        await self._send(text)
