from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.keyboards.callback_factories import EpisodeCB, NavCB, QualityCB, SeasonCB, BatchDownloadCB


def build_season_kb(
    series_id: int, 
    seasons: list[dict], 
    track_button: InlineKeyboardButton | None = None
) -> InlineKeyboardMarkup:
    """
    Builds the season-picker keyboard.
    seasons: [{"id": int, "season_number": int}, ...]
    """
    builder = InlineKeyboardBuilder()
    for season in seasons:
        builder.button(
            text=f"📺 Season {season['season_number']}",
            callback_data=SeasonCB(series_id=series_id, season_id=season["id"]),
        )
    builder.adjust(2, repeat=True)
    
    # Last row(s): Track Button (if provided) and Close button
    footer_row = []
    if track_button:
        footer_row.append(track_button)
    footer_row.append(
        InlineKeyboardButton(
            text="❌ Close",
            callback_data=NavCB(action="close", target_id=series_id).pack(),
        )
    )
    builder.row(*footer_row)
    return builder.as_markup()


def build_quality_kb(season_id: int, series_id: int, qualities: list[str]) -> InlineKeyboardMarkup:
    """
    Builds the quality-picker keyboard.
    qualities: list of quality strings e.g. ["480p", "720p", "1080p", "1440p", "4K"]
    """
    QUALITY_LABELS: dict[str, str] = {
        "720p": "🎥 720p HD",
        "1080p": "🎥 1080p Full HD",
        "1440p": "🎥 1440p Quad HD",
        "4K": "🎥 2160p 4K UHD",
        "2160p": "🎥 2160p 4K UHD",
        "480p": "📱 480p SD",
        "Unknown": "📁 Unknown Quality",
    }
    builder = InlineKeyboardBuilder()
    for q in qualities:
        label = QUALITY_LABELS.get(q, f"📁 {q}")
        builder.button(
            text=label,
            callback_data=QualityCB(season_id=season_id, quality=q),
        )
    builder.button(
        text="◀️ Back to Seasons",
        callback_data=NavCB(action="to_seasons", target_id=series_id),
    )
    builder.adjust(2, repeat=True)
    return builder.as_markup()


def build_episode_kb(
    season_id: int,
    episodes: list[dict],
    series_id: int,
    quality: str,
) -> InlineKeyboardMarkup:
    """
    Builds the 2-column episode grid keyboard.
    """
    builder = InlineKeyboardBuilder()
    
    # 1. Combined Season File Button
    combined_ep = next((ep for ep in episodes if ep["episode_number"] == 0), None)
    if combined_ep:
        builder.button(
            text="📦 Combined Season File",
            callback_data=EpisodeCB(season_id=season_id, episode_id=combined_ep["id"]),
        )
        
    # 2. Batch Download Button
    builder.button(
        text="📦 Complete Season (Batch Download)",
        callback_data=BatchDownloadCB(season_id=season_id, quality=quality),
    )
    
    # 3. Episode Grid
    for ep in episodes:
        ep_num = ep["episode_number"]
        if ep_num == 0:
            continue
        builder.button(
            text=f"Ep {ep_num}",
            callback_data=EpisodeCB(season_id=season_id, episode_id=ep["id"]),
        )
        
    # Adjust layout: full width for combined and batch buttons, then 2 columns
    adjustments = []
    if combined_ep:
        adjustments.append(1)
    adjustments.append(1)  # For Batch Download
    
    # We can pass the sizes to builder.adjust, but since the rest is 2-col, we can do builder.adjust(*adjustments, 2)
    builder.adjust(*adjustments, 2)
    
    # 3. Footers
    builder.row(
        InlineKeyboardButton(
            text="⬅️ Back to Quality",
            callback_data=NavCB(action="to_qualities", target_id=season_id).pack()
        ),
        InlineKeyboardButton(
            text="❌ Close",
            callback_data=NavCB(action="close", target_id=series_id).pack()
        )
    )
    
    return builder.as_markup()


def build_search_results_kb(results: list[dict]) -> InlineKeyboardMarkup:
    """
    Inline keyboard when multiple series match a search query.
    results: [{"id", "title"}, ...]
    """
    builder = InlineKeyboardBuilder()
    for series in results:
        builder.button(
            text=series["title"],
            callback_data=SeasonCB(series_id=series["id"], season_id=0),
        )
    builder.adjust(1)
    return builder.as_markup()

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from bot.database.models.tracked_show import TrackedShow

async def get_track_button(
    session: AsyncSession, user_id: int, series_id: int
) -> InlineKeyboardButton:
  stmt = select(TrackedShow).where(
      TrackedShow.user_id == user_id, TrackedShow.series_id == series_id
  )
  is_tracked = (await session.execute(stmt)).scalar_one_or_none() is not None

  if is_tracked:
    return InlineKeyboardButton(
        text="🔕 Untrack Show", callback_data=f"untrack_show:{series_id}"
    )
  return InlineKeyboardButton(
      text="🔔 Track Show", callback_data=f"track_show:{series_id}"
  )
