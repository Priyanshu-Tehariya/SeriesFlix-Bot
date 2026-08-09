from __future__ import annotations

import structlog
from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.filters.admin import IsAdmin
from bot.keyboards.admin_kb import build_request_moderation_kb
from bot.keyboards.callback_factories import AdminDeleteFileCB, AdminReqCB
from bot.loader import redis_client
from bot.services.cache_service import CacheService
from bot.services.request_service import RequestService
from bot.database.repositories.episode_repo import EpisodeRepository

logger = structlog.get_logger(__name__)

router = Router(name="admin_moderation")


@router.callback_query(AdminReqCB.filter(), IsAdmin())
async def on_admin_request_action(
    callback: CallbackQuery,
    callback_data: AdminReqCB,
    session: AsyncSession,
) -> None:
    """Handle admin tap on Uploaded / Coming Soon / Reject buttons."""
    await callback.answer()

    if callback.from_user is None:
        return

    svc = RequestService(session, callback.bot)  # type: ignore[arg-type]
    success, message_text = await svc.handle_admin_action(
        request_id=callback_data.request_id,
        action=callback_data.action,
        admin_id=callback.from_user.id,
    )

    # Edit the admin card to reflect the new status
    status_labels = {
        "uploaded": "✅ UPLOADED",
        "coming_soon": "🔜 COMING SOON",
        "reject": "❌ REJECTED",
    }
    status_label = status_labels.get(callback_data.action, callback_data.action.upper())

    if callback.message:
        try:
            current_text = callback.message.html_text or ""
            
            import re
            # Remove any existing admin signature to prevent duplicates
            clean_text = re.sub(r"\n\nBy admin:.*", "", current_text, flags=re.DOTALL)
            
            # Replace the Status line completely
            new_text = re.sub(
                r"Status:\s*.*", 
                f"Status: <b>{status_label}</b>", 
                clean_text
            )

            new_text += f"\n\nBy admin: <a href='tg://user?id={callback.from_user.id}'>{callback.from_user.full_name}</a>"
            
            await callback.message.edit_text(new_text, parse_mode="HTML")
        except TelegramBadRequest as e:
            logger.warning("admin_card_edit_failed", error=str(e))


@router.callback_query(AdminDeleteFileCB.filter(F.source == "log"), IsAdmin())
async def on_admin_delete_file(
    callback: CallbackQuery,
    callback_data: AdminDeleteFileCB,
    session: AsyncSession,
) -> None:
    """Handle admin tap on 'Delete File' from the index log card."""
    repo = EpisodeRepository(session)
    result = await repo.delete_by_id(callback_data.episode_id)

    if result:
        series_id, season_id = result
        cache = CacheService(redis_client)
        await cache.invalidate_prefix("search:")
        await cache.invalidate_prefix(f"series:{series_id}:")
        await cache.invalidate_prefix(f"season:{season_id}:")

    if callback.message:
        try:
            await callback.message.delete()
        except TelegramBadRequest:
            pass

    await callback.answer("File removed from database and log card deleted!", show_alert=True)
