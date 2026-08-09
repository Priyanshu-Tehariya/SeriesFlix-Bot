from __future__ import annotations

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

logger = structlog.get_logger(__name__)

from bot.filters.chat_type import ChatTypeFilter
from bot.keyboards.inline.navigation_kb import build_season_kb, build_search_results_kb, get_track_button
from bot.handlers.user.navigation import _build_series_caption
from bot.services.cache_service import CacheService
from bot.services.navigation_service import NavigationService
from bot.services.search_service import SearchService
from bot.services.tmdb_service import fetch_poster_file
from bot.states.request_states import RequestFSM
from bot.utils.i18n import t
from bot.utils.text_formatters import truncate, bold

router = Router(name="user_search")
router.message.filter(ChatTypeFilter(ChatType.PRIVATE))


async def perform_search(
    query: str,
    user_id: int,
    answer_func,
    answer_photo_func,
    session: AsyncSession,
) -> None:
    """Core search logic usable from both text messages and FSub callbacks."""
    from bot.loader import redis_client
    cache = CacheService(redis_client)
    svc = SearchService(session, cache)
    results = await svc.search(query, user_id)

    if not results:
        await answer_func(t("search_no_results", query=query), parse_mode="HTML")
        return

    # Single result → go straight to season picker
    if len(results) == 1:
        series = results[0]
        nav_svc = NavigationService(session, cache)
        
        # Fetch TMDB metadata first!
        series_meta = await nav_svc.get_series_meta(series["id"])
        if series_meta:
            series = series_meta
            
        seasons = await nav_svc.get_seasons(series["id"])
        caption = _build_series_caption(series, seasons)
        
        track_button = await get_track_button(session, user_id, series["id"])
        kb = build_season_kb(series["id"], seasons, track_button)

        poster_url = series.get("poster_url")
        poster_file, tmdb_404 = await fetch_poster_file(poster_url)

        # If TMDB returned 404 for this poster path, purge DB + cache and re-fetch
        if tmdb_404 and series.get("id"):
            from bot.database.repositories.series_repo import SeriesRepository
            from bot.services.tmdb_service import TMDBClient, get_poster_url as gpu, POSTER_BROKEN_SENTINEL
            repo = SeriesRepository(session)
            db_series = await repo.get_by_id(series["id"])
            if db_series:
                old_path = db_series.poster_url
                db_series.poster_url = None
                await session.commit()
                logger.warning(f"Purged stale poster_url '{old_path}' from DB for series {series['id']}")

                # Delete stale cache keys
                from bot.utils.text import normalize_query
                await cache.delete(CacheService.meta_key(series["id"]))
                await cache.delete(CacheService.search_key(normalize_query(query)))

                # Re-fetch from TMDB for a fresh poster path
                tmdb_fresh = await TMDBClient.search_series(db_series.title)
                if tmdb_fresh and tmdb_fresh.get("poster_url"):
                    fresh_url = tmdb_fresh["poster_url"]
                    # Extract raw filenames to compare — avoid re-saving the same broken path
                    old_file = old_path.split("/")[-1] if old_path else ""
                    fresh_file = fresh_url.split("/")[-1] if fresh_url else ""
                    if fresh_file and fresh_file != old_file:
                        db_series.poster_url = fresh_url
                        await session.commit()
                        logger.info(f"Refreshed poster_url to '{fresh_url}' for series {series['id']}")
                        # Re-download the fresh poster
                        poster_file, _ = await fetch_poster_file(fresh_url)
                    else:
                        # Permanently mark as broken to skip all future TMDB calls
                        db_series.poster_url = POSTER_BROKEN_SENTINEL
                        await session.commit()
                        logger.warning(f"Marked series {series['id']} poster as '{POSTER_BROKEN_SENTINEL}' — TMDB has no valid image.")
                else:
                    # TMDB returned nothing — mark as broken
                    db_series.poster_url = POSTER_BROKEN_SENTINEL
                    await session.commit()
                    logger.warning(f"Marked series {series['id']} poster as '{POSTER_BROKEN_SENTINEL}' — TMDB returned no results.")

        if poster_file:
            await answer_photo_func(
                photo=poster_file,
                caption=caption,
                reply_markup=kb,
                parse_mode="HTML",
            )
            return

        # Fallback: Send plain text card if poster is missing
        await answer_func(caption, reply_markup=kb, parse_mode="HTML")
    else:
        # Multiple results → disambiguation keyboard
        kb = build_search_results_kb(results)
        await answer_func(
            t("search_results", query=query),
            reply_markup=kb,
            parse_mode="HTML",
        )


@router.message(F.text & ~F.text.startswith("/"))
async def handle_search(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    redis: object,
) -> None:
    """Handle any non-command text as a series search query."""
    if message.text is None:
        return

    # Don't intercept FSM states
    current_state = await state.get_state()
    if current_state == RequestFSM.waiting_for_query.state:
        return

    query = message.text.strip()
    if not query:
        return

    user_id = message.from_user.id if message.from_user else 0  # type: ignore[union-attr]

    await perform_search(
        query=query,
        user_id=user_id,
        answer_func=message.answer,
        answer_photo_func=message.answer_photo,
        session=session,
    )

