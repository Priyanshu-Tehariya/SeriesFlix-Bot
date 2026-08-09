from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy.ext.asyncio import AsyncSession
from bot.handlers.user.search import perform_search
from bot.services.tmdb_service import TMDBClient

discovery_router = Router(name="discovery")


def build_shows_list_kb(shows: list[dict]) -> InlineKeyboardMarkup:
  buttons = []
  for show in shows:
    name = show.get("name") or show.get("original_name") or "Unknown"
    first_air = show.get("first_air_date", "")
    year = f" ({first_air[:4]})" if first_air and len(first_air) >= 4 else ""

    # Pass title query so clicking the button triggers your existing search flow directly
    buttons.append([
      InlineKeyboardButton(
          text=f"📺 {name}{year}", callback_data=f"search:{name.lower()[:30]}"
      )
    ])
  return InlineKeyboardMarkup(inline_keyboard=buttons)


@discovery_router.message(Command("trending"))
async def cmd_trending(message: Message):
  shows = await TMDBClient.get_trending_shows()
  if not shows:
    await message.answer("⚠️ Unable to fetch trending shows right now.")
    return

  DIVIDER = "<b>─────────────────────────</b>"
  text = (
      "<b>🔥 Top Trending Shows Today</b>\n"
      f"{DIVIDER}\n"
      "Tap any show below to view full details:"
  )
  await message.answer(
      text, reply_markup=build_shows_list_kb(shows), parse_mode="HTML"
  )


@discovery_router.message(Command("popular"))
async def cmd_popular(message: Message):
  shows = await TMDBClient.get_popular_shows()
  if not shows:
    await message.answer("⚠️ Unable to fetch popular shows right now.")
    return

  DIVIDER = "<b>─────────────────────────</b>"
  text = (
      "<b>⭐ Most Popular Shows</b>\n"
      f"{DIVIDER}\n"
      "Tap any show below to view full details:"
  )
  await message.answer(
      text, reply_markup=build_shows_list_kb(shows), parse_mode="HTML"
  )

@discovery_router.callback_query(F.data.startswith("search:"))
async def cb_discovery_show_select(
    callback: CallbackQuery, session: AsyncSession
):
  query = callback.data.split("search:", 1)[1].strip()
  await callback.answer(f"🔎 Fetching details for {query}...")

  # Execute search via existing search pipeline
  await perform_search(
      query=query,
      user_id=callback.from_user.id,
      answer_func=callback.message.answer,
      answer_photo_func=callback.message.answer_photo,
      session=session,
  )
