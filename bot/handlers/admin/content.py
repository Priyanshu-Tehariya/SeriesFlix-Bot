from __future__ import annotations

import structlog
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models.episode import Episode
from bot.database.models.season import Season
from bot.database.repositories.episode_repo import EpisodeRepository
from bot.database.repositories.series_repo import SeriesRepository
from bot.filters.admin import IsAdmin
from bot.keyboards.callback_factories import AdminDeleteFileCB
from bot.loader import redis_client
from bot.services.admin_log_service import AdminLogService
from bot.services.cache_service import CacheService

logger = structlog.get_logger(__name__)

router = Router(name="admin_content")
router.message.filter(IsAdmin())


@router.message(Command("delete"))
async def cmd_delete(message: Message, session: AsyncSession) -> None:
    """
    /delete <series_id | series title>

    Deletes a series and all its seasons/episodes from the database (CASCADE),
    flushes related Redis cache keys, and logs the action to LOG_CHANNEL_ID.

    Examples:
        /delete 42
        /delete Breaking Bad
    """
    if message.text is None or message.from_user is None:
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "Usage: /delete <series_id | series title>\n"
            "Examples:\n"
            "  <code>/delete 42</code>\n"
            "  <code>/delete Breaking Bad</code>",
            parse_mode="HTML",
        )
        return

    raw_query: str = parts[1].strip()
    series_repo = SeriesRepository(session)

    result = await series_repo.delete_by_id_or_title(raw_query)

    if result is None:
        await message.answer(
            f"❌ No series found matching <b>{raw_query}</b>.",
            parse_mode="HTML",
        )
        return

    # --- Flush Redis cache for this series ---
    cache = CacheService(redis_client)
    await cache.invalidate_prefix("search:")
    await cache.invalidate_prefix(f"series:{result.series_id}:")
    # Episode caches are keyed on season IDs — clear the whole season namespace
    # (season IDs are no longer accessible after deletion, so we broadcast a broader wipe)
    await cache.invalidate_prefix("season:")

    # --- Confirm to admin ---
    await message.answer(
        f"🗑 <b>Deleted:</b> {result.series_title}\n"
        f"Episodes removed: <b>{result.deleted_episodes}</b>",
        parse_mode="HTML",
    )

    # --- Log to LOG_CHANNEL_ID ---
    admin_log = AdminLogService(message.bot)  # type: ignore[arg-type]
    await admin_log.log_deletion(
        admin_id=message.from_user.id,
        series_title=result.series_title,
        series_id=result.series_id,
        deleted_episodes=result.deleted_episodes,
    )

    logger.info(
        "series_deleted",
        admin_id=message.from_user.id,
        series_id=result.series_id,
        series_title=result.series_title,
        deleted_episodes=result.deleted_episodes,
    )


@router.message(Command("manage"))
async def cmd_manage(message: Message, session: AsyncSession) -> None:
    """
    /manage <series_id | series title>
    Displays a list of episodes with delete buttons.
    """
    if message.text is None or message.from_user is None:
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Usage: /manage <series_id | series title>")
        return

    raw_query: str = parts[1].strip()
    series_repo = SeriesRepository(session)
    series = await series_repo.get_by_id_or_title(raw_query)

    if not series:
        await message.answer(f"❌ No series found matching <b>{raw_query}</b>.", parse_mode="HTML")
        return

    # Fetch episodes
    result = await session.execute(
        select(Episode)
        .join(Season)
        .where(Season.series_id == series.id)
        .options(joinedload(Episode.season))
        .order_by(Season.season_number, Episode.episode_number)
    )
    episodes = result.scalars().all()

    if not episodes:
        await message.answer(f"Series <b>{series.title}</b> has no episodes.", parse_mode="HTML")
        return

    keyboard = []
    # Limit to 90 to avoid Telegram 100 button limit
    for ep in episodes[:90]:
        ep_label = f"S{ep.season.season_number:02d}E{ep.episode_number:02d}" if ep.episode_number > 0 else f"S{ep.season.season_number:02d} Complete"
        btn_text = f"{ep_label} [{ep.quality.value}] 🗑"
        cb_data = AdminDeleteFileCB(episode_id=ep.id, source="manage").pack()
        keyboard.append([InlineKeyboardButton(text=btn_text, callback_data=cb_data)])
        
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    msg_text = f"⚙️ <b>Managing:</b> {series.title}\nSelect an episode variant to delete it."
    if len(episodes) > 90:
        msg_text += "\n<i>(Showing first 90 episodes)</i>"

    await message.answer(msg_text, parse_mode="HTML", reply_markup=reply_markup)


@router.callback_query(AdminDeleteFileCB.filter(F.source == "manage"))
async def on_manage_delete_file(
    callback: CallbackQuery,
    callback_data: AdminDeleteFileCB,
    session: AsyncSession,
) -> None:
    repo = EpisodeRepository(session)
    result = await repo.delete_by_id(callback_data.episode_id)

    if result:
        series_id, season_id = result
        cache = CacheService(redis_client)
        await cache.invalidate_prefix("search:")
        await cache.invalidate_prefix(f"series:{series_id}:")
        await cache.invalidate_prefix(f"season:{season_id}:")

    # Remove the button from the keyboard
    if callback.message and callback.message.reply_markup:
        keyboard = callback.message.reply_markup.inline_keyboard
        new_keyboard = []
        for row in keyboard:
            new_row = [btn for btn in row if btn.callback_data != callback_data.pack()]
            if new_row:
                new_keyboard.append(new_row)
        
        try:
            from aiogram.exceptions import TelegramBadRequest
            await callback.message.edit_reply_markup(
                reply_markup=InlineKeyboardMarkup(inline_keyboard=new_keyboard)
            )
        except TelegramBadRequest:
            pass

    await callback.answer("File deleted!", show_alert=False)


@router.message(Command("prune_older_than"))
async def cmd_prune_older_than(message: Message, session: AsyncSession) -> None:
    """
    /prune_older_than <days>
    Deletes all files older than the specified number of days.
    """
    if message.text is None or message.from_user is None:
        return

    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("Usage: /prune_older_than <days>")
        return

    days = int(parts[1])
    repo = EpisodeRepository(session)
    deleted_count = await repo.delete_older_than(days)

    cache = CacheService(redis_client)
    await cache.invalidate_prefix("search:")
    await cache.invalidate_prefix("series:")
    await cache.invalidate_prefix("season:")

    await message.answer(f"🧹 Purged {deleted_count} files older than {days} days.")

    admin_log = AdminLogService(message.bot)  # type: ignore[arg-type]
    await admin_log.log_bulk_deletion(
        admin_id=message.from_user.id,
        days=days,
        deleted_count=deleted_count,
    )
