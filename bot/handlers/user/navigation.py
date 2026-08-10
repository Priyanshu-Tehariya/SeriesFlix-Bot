from __future__ import annotations

import html
import structlog
from aiogram import Bot, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InputMediaPhoto, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.callback_factories import EpisodeCB, NavCB, QualityCB, SeasonCB, BatchDownloadCB, CombinedDownloadCB
from bot.keyboards.inline.navigation_kb import (
    build_episode_kb,
    build_quality_kb,
    build_season_kb,
    get_track_button,
)
from bot.loader import redis_client
from bot.services.cache_service import CacheService
from bot.services.navigation_service import NavigationService
from bot.utils.text_formatters import format_file_size, truncate, build_episode_caption
from bot.config import settings

logger = structlog.get_logger(__name__)

router = Router(name="user_navigation")


def _get_nav_svc(session: AsyncSession) -> NavigationService:
    return NavigationService(session, CacheService(redis_client))


# ---------------------------------------------------------------------------
# SeasonCB: Series page → Season picker
# ---------------------------------------------------------------------------

@router.callback_query(SeasonCB.filter())
async def on_season_selected(
    callback: CallbackQuery,
    callback_data: SeasonCB,
    session: AsyncSession,
) -> None:
    await callback.answer()
    nav = _get_nav_svc(session)

    # If season_id == 0 it means we came from search disambiguation — load seasons
    if callback_data.season_id == 0:
        series_meta = await nav.get_series_meta(callback_data.series_id)
        if not series_meta:
            await callback.answer("Series not found.", show_alert=True)
            return
        seasons = await nav.get_seasons(callback_data.series_id)
        user_id = callback.from_user.id
        track_button = await get_track_button(session, user_id, callback_data.series_id)
        kb = build_season_kb(callback_data.series_id, seasons, track_button)
        caption = _build_series_caption(series_meta, seasons)
        if callback.message is None:
            return
        await smart_edit_message(
            message=callback.message,
            text=caption,
            reply_markup=kb,
            poster_url=series_meta.get("poster_url"),
        )
        return

    # Normal case: user tapped a season
    series_meta = await nav.get_series_meta(callback_data.series_id)
    qualities = await nav.get_qualities(callback_data.season_id)

    if not qualities:
        await callback.answer("No content available for this season yet.", show_alert=True)
        return

    kb = build_quality_kb(
        season_id=callback_data.season_id,
        series_id=callback_data.series_id,
        qualities=qualities,
    )
    series_title = series_meta["title"] if series_meta else "Series"
    season_number = _find_season_number(await nav.get_seasons(callback_data.series_id), callback_data.season_id)
    caption = f"📺 <b>{series_title}</b> — Season {season_number}\n\nSelect quality:"

    if callback.message is None:
        return
    await smart_edit_message(
        message=callback.message,
        text=caption,
        reply_markup=kb,
        poster_url=series_meta.get("poster_url") if series_meta else None,
    )


# ---------------------------------------------------------------------------
# QualityCB: Season page → Episode grid
# ---------------------------------------------------------------------------

@router.callback_query(QualityCB.filter())
async def on_quality_selected(
    callback: CallbackQuery,
    callback_data: QualityCB,
    session: AsyncSession,
) -> None:
    await callback.answer()
    nav = _get_nav_svc(session)

    episodes = await nav.get_episodes(callback_data.season_id, callback_data.quality)
    if not episodes:
        await callback.answer("No episodes available for this quality.", show_alert=True)
        return

    # We need series_id for back navigation; look up via season's series
    from bot.database.repositories.season_repo import SeasonRepository
    season = await SeasonRepository(session).get_by_id(callback_data.season_id)
    series_id = season.series_id if season else 0
    season_number = season.season_number if season else 0

    series_meta = await nav.get_series_meta(series_id)
    series_title = series_meta["title"] if series_meta else "Series"

    kb = build_episode_kb(
        season_id=callback_data.season_id,
        episodes=episodes,
        series_id=series_id,
        quality=callback_data.quality,
    )
    caption = (
        f"📺 <b>{series_title}</b> — S{season_number:02d} [{callback_data.quality}]\n\n"
        f"Select an episode:"
    )

    if callback.message is None:
        return
    await smart_edit_message(
        message=callback.message,
        text=caption,
        reply_markup=kb,
        poster_url=series_meta.get("poster_url") if series_meta else None,
    )


# ---------------------------------------------------------------------------
# EpisodeCB: Episode grid → deliver file
# ---------------------------------------------------------------------------

@router.callback_query(EpisodeCB.filter())
async def on_episode_selected(
    callback: CallbackQuery,
    callback_data: EpisodeCB,
    session: AsyncSession,
) -> None:
    await callback.answer("Sending file…")
    nav = _get_nav_svc(session)

    ep = await nav.get_episode_for_delivery(callback_data.episode_id)
    if ep is None:
        await callback.answer("File is not available.", show_alert=True)
        return

    from bot.utils.text_formatters import clean_language_display
    import html
    
    caption = build_episode_caption(ep, settings.AUTO_DELETE_SECONDS)

    # Deliver file — try as video first, fall back to document
    if callback.message is None or callback.from_user is None:
        return

    try:
        sent_msg = await callback.message.bot.send_document(
            chat_id=callback.from_user.id,
            document=ep["file_id"],
            caption=caption,
            parse_mode="HTML"
        )
        if settings.AUTO_DELETE_SECONDS > 0:
            import asyncio
            asyncio.create_task(
                schedule_auto_delete(
                    callback.message.bot,
                    callback.from_user.id,
                    sent_msg.message_id,
                    settings.AUTO_DELETE_SECONDS
                )
            )
    except Exception as e:
        import structlog
        structlog.get_logger(__name__).error("delivery_failed", error=str(e), ep_id=ep["id"])
        await callback.message.answer("Failed to deliver file. It might have been deleted from the index channel.")

    await nav.increment_download(ep["id"])


# ---------------------------------------------------------------------------
# CombinedDownloadCB: Deliver all combined/part files for a season
# ---------------------------------------------------------------------------

@router.callback_query(CombinedDownloadCB.filter())
async def on_combined_download_selected(
    callback: CallbackQuery,
    callback_data: CombinedDownloadCB,
    session: AsyncSession,
) -> None:
    await callback.answer("Preparing combined files…")
    nav = _get_nav_svc(session)

    episodes = await nav.get_episodes(callback_data.season_id, callback_data.quality)
    if not episodes:
        await callback.answer("No files available for this quality.", show_alert=True)
        return

    # Filter out individual episodes, keep only episode_number == 0
    episodes = [ep for ep in episodes if ep["episode_number"] == 0]

    # No need to sort by episode number since they are all 0, but they'll be sent in the order retrieved
    # Usually ordered by ID implicitly in the DB if they have same number

    if not episodes:
        await callback.answer("No combined files available.", show_alert=True)
        return

    if callback.message is None or callback.from_user is None:
        return

    status_msg = await callback.message.answer(f"📦 Starting delivery of {len(episodes)} combined file(s)...")

    import asyncio
    import html
    from bot.utils.text_formatters import clean_language_display

    for ep_dict in episodes:
        ep = await nav.get_episode_for_delivery(ep_dict["id"])
        if not ep:
            continue
            
        caption = build_episode_caption(ep, settings.AUTO_DELETE_SECONDS)
        
        try:
            sent_msg = await callback.message.bot.send_document(
                chat_id=callback.from_user.id,
                document=ep["file_id"],
                caption=caption,
                parse_mode="HTML"
            )
            if settings.AUTO_DELETE_SECONDS > 0:
                asyncio.create_task(
                    schedule_auto_delete(
                        callback.message.bot,
                        callback.from_user.id,
                        sent_msg.message_id,
                        settings.AUTO_DELETE_SECONDS
                    )
                )
            await nav.increment_download(ep["id"])
        except Exception as e:
            import structlog
            structlog.get_logger(__name__).error("combined_delivery_failed", error=str(e), ep_id=ep["id"])
            
        await asyncio.sleep(0.5)
        
    await status_msg.delete()


# ---------------------------------------------------------------------------
# BatchDownloadCB: Deliver all episodes for a season sequentially
# ---------------------------------------------------------------------------

@router.callback_query(BatchDownloadCB.filter())
async def on_batch_download_selected(
    callback: CallbackQuery,
    callback_data: BatchDownloadCB,
    session: AsyncSession,
) -> None:
    await callback.answer("Preparing batch download…")
    nav = _get_nav_svc(session)

    episodes = await nav.get_episodes(callback_data.season_id, callback_data.quality)
    if not episodes:
        await callback.answer("No episodes available for this quality.", show_alert=True)
        return

    # Filter out the "Complete Season" zip if it exists, since we are sending individuals
    episodes = [ep for ep in episodes if ep["episode_number"] != 0]
    
    # Sort them by episode number
    episodes.sort(key=lambda x: x["episode_number"])

    if not episodes:
        await callback.answer("No individual episodes available.", show_alert=True)
        return

    if callback.message is None or callback.from_user is None:
        return

    status_msg = await callback.message.answer(f"📦 Starting batch delivery of {len(episodes)} episodes...")

    import asyncio
    import html
    from bot.utils.text_formatters import clean_language_display

    for ep_dict in episodes:
        ep = await nav.get_episode_for_delivery(ep_dict["id"])
        if not ep:
            continue
            
        caption = build_episode_caption(ep, settings.AUTO_DELETE_SECONDS)
        
        try:
            sent_msg = await callback.message.bot.send_document(
                chat_id=callback.from_user.id,
                document=ep["file_id"],
                caption=caption,
                parse_mode="HTML"
            )
            if settings.AUTO_DELETE_SECONDS > 0:
                asyncio.create_task(
                    schedule_auto_delete(
                        callback.message.bot,
                        callback.from_user.id,
                        sent_msg.message_id,
                        settings.AUTO_DELETE_SECONDS
                    )
                )
            await nav.increment_download(ep["id"])
        except Exception as e:
            import structlog
            structlog.get_logger(__name__).error("batch_delivery_failed", error=str(e), ep_id=ep["id"])
            
        await asyncio.sleep(0.5)
        
    await status_msg.delete()


# ---------------------------------------------------------------------------
# NavCB: Back navigation
# ---------------------------------------------------------------------------

@router.callback_query(NavCB.filter())
async def on_nav(
    callback: CallbackQuery,
    callback_data: NavCB,
    session: AsyncSession,
) -> None:
    await callback.answer()
    nav = _get_nav_svc(session)

    match callback_data.action:
        case "to_seasons":
            series_id = callback_data.target_id
            series_meta = await nav.get_series_meta(series_id)
            seasons = await nav.get_seasons(series_id)
            user_id = callback.from_user.id
            track_button = await get_track_button(session, user_id, series_id)
            kb = build_season_kb(series_id, seasons, track_button)
            caption = _build_series_caption(series_meta or {}, seasons)
            if callback.message is None:
                return
            await smart_edit_message(
                message=callback.message,
                text=caption,
                reply_markup=kb,
                poster_url=series_meta.get("poster_url") if series_meta else None,
            )

        case "to_qualities":
            season_id = callback_data.target_id
            from bot.database.repositories.season_repo import SeasonRepository
            season = await SeasonRepository(session).get_by_id(season_id)
            if season is None:
                return
            series_meta = await nav.get_series_meta(season.series_id)
            qualities = await nav.get_qualities(season_id)
            kb = build_quality_kb(
                season_id=season_id,
                series_id=season.series_id,
                qualities=qualities,
            )
            series_title = series_meta["title"] if series_meta else "Series"
            caption = f"📺 <b>{series_title}</b> — Season {season.season_number}\n\nSelect quality:"
            if callback.message is None:
                return
            await smart_edit_message(
                message=callback.message,
                text=caption,
                reply_markup=kb,
                poster_url=series_meta.get("poster_url") if series_meta else None,
            )

        case "close":
            if callback.message:
                try:
                    await callback.message.delete()
                except TelegramBadRequest:
                    pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_season_number(seasons: list[dict], season_id: int) -> int:
    for s in seasons:
        if s["id"] == season_id:
            return s["season_number"]
    return 0


def _build_series_caption(series: dict, seasons: list[dict]) -> str:
    title = series.get("title", "Unknown Series")
    year = f" ({series['year']})" if series.get("year") else ""
    rating = series.get("rating", "N/A")
    genres = series.get("genres", "N/A")
    summary = series.get("summary", "No overview available.")
    season_count = len(seasons)

    # Standardized 25-character divider for desktop & mobile viewports
    DIVIDER = "<b>─────────────────────────</b>"

    caption_lines = [
        f"<b>🎬 {title}{year}</b>",
        DIVIDER,
        f"<b>⭐ Rating:</b> {rating}",
        f"<b>🎭 Genre:</b> {genres}",
        f"<b>📅 Seasons:</b> {season_count} Available",
        "",
        f"<b>📝 Overview:</b>",
        f"<blockquote>{truncate(summary, 250)}</blockquote>",
        "",
        DIVIDER,
        "<b>👇 Select a season below to proceed:</b>",
    ]

    return "\n".join(caption_lines)


async def smart_edit_message(
    message: Message,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    parse_mode: str = "HTML",
    poster_url: str | None = None,
) -> None:
    """Edits a message's text or caption depending on whether it has media, handling unchanged errors."""
    deleted = False
    try:
        if poster_url:
            from bot.services.tmdb_service import fetch_poster_file
            poster_file, _tmdb_404 = await fetch_poster_file(poster_url)
            if poster_file:
                from aiogram.types import InputMediaPhoto
                if message.photo or message.video or message.document:
                    await message.edit_media(
                        media=InputMediaPhoto(media=poster_file, caption=text, parse_mode=parse_mode),
                        reply_markup=reply_markup
                    )
                else:
                    await message.delete()
                    deleted = True
                    await message.answer_photo(
                        photo=poster_file,
                        caption=text,
                        reply_markup=reply_markup,
                        parse_mode=parse_mode
                    )
                return

        # Fallback to text card
        if deleted:
            await message.answer(text=text, reply_markup=reply_markup, parse_mode=parse_mode)
        elif message.photo or message.video or message.document:
            await message.edit_caption(caption=text, reply_markup=reply_markup, parse_mode=parse_mode)
        else:
            await message.edit_text(text=text, reply_markup=reply_markup, parse_mode=parse_mode)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e).lower():
            raise


async def schedule_auto_delete(bot: Bot, chat_id: int, message_id: int, seconds: int) -> None:
    """Sleeps for the specified time and then attempts to delete the message."""
    import asyncio
    await asyncio.sleep(seconds)
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as e:
        logger.warning(
            f"Failed to delete card/message {message_id} in {chat_id}: {e}"
        )

