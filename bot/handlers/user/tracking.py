from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from bot.database.models.tracked_show import TrackedShow
from bot.database.models.series import Series

tracking_router = Router(name="show_tracking")


@tracking_router.callback_query(F.data.startswith("track_show:"))
async def cb_track_show(callback: CallbackQuery, session: AsyncSession):
  from bot.services.navigation_service import NavigationService
  from bot.services.cache_service import CacheService
  from bot.loader import redis_client
  from bot.keyboards.inline.navigation_kb import build_season_kb
  series_id = int(callback.data.split("track_show:", 1)[1])
  user_id = callback.from_user.id

  existing = (
      await session.execute(
          select(TrackedShow).where(
              TrackedShow.user_id == user_id,
              TrackedShow.series_id == series_id,
          )
      )
  ).scalar_one_or_none()

  if not existing:
    session.add(TrackedShow(user_id=user_id, series_id=series_id))
    await session.commit()
    
    # Update inline keyboard
    nav = NavigationService(session, CacheService(redis_client))
    seasons = await nav.get_seasons(series_id)
    track_button = InlineKeyboardButton(text="🔕 Untrack Show", callback_data=f"untrack_show:{series_id}")
    await callback.message.edit_reply_markup(
        reply_markup=build_season_kb(series_id, seasons, track_button)
    )

    await callback.answer(
        "🔔 You are now tracking this show! You will be notified when new"
        " episodes arrive.",
        show_alert=True,
    )
  else:
    await callback.answer(
        "ℹ️ You are already tracking this show.", show_alert=True
    )


@tracking_router.callback_query(F.data.startswith("untrack_show:"))
async def cb_untrack_show(callback: CallbackQuery, session: AsyncSession):
  series_id = int(callback.data.split("untrack_show:", 1)[1])
  user_id = callback.from_user.id

  await session.execute(
      delete(TrackedShow).where(
          TrackedShow.user_id == user_id, TrackedShow.series_id == series_id
      )
  )
  await session.commit()

  # Update inline keyboard
  from bot.services.navigation_service import NavigationService
  from bot.services.cache_service import CacheService
  from bot.loader import redis_client
  from bot.keyboards.inline.navigation_kb import build_season_kb
  nav = NavigationService(session, CacheService(redis_client))
  seasons = await nav.get_seasons(series_id)
  track_button = InlineKeyboardButton(text="🔔 Track Show", callback_data=f"track_show:{series_id}")
  await callback.message.edit_reply_markup(
      reply_markup=build_season_kb(series_id, seasons, track_button)
  )

  await callback.answer(
      "🔕 Show removed from tracking list.", show_alert=True
  )


@tracking_router.message(Command("tracked"))
@tracking_router.message(Command("watchlist"))
async def cmd_list_tracked(message: Message, session: AsyncSession):
  user_id = message.from_user.id

  # Fetch series IDs tracked by the user
  stmt = (
      select(Series.id, Series.title)
      .join(TrackedShow, Series.id == TrackedShow.series_id)
      .where(TrackedShow.user_id == user_id)
  )
  results = (await session.execute(stmt)).all()

  if not results:
    await message.answer(
        "<b>🔔 Tracked Series</b>\n"
        "─────────────────────────\n"
        "You aren't tracking any shows yet!\n\n"
        "Tap the <b>🔔 Track Show</b> button on any series card to get episode alerts.",
        parse_mode="HTML",
    )
    return

  buttons = []
  for series_id, title in results:
    buttons.append([
        InlineKeyboardButton(
            text=f"📺 {title}", callback_data=f"search:{title.lower()[:30]}"
        )
    ])

  keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
  DIVIDER = "<b>─────────────────────────</b>"
  await message.answer(
      f"<b>🔔 Your Tracked Series</b>\n{DIVIDER}\nTap any show to view seasons and episodes:",
      reply_markup=keyboard,
      parse_mode="HTML",
  )
