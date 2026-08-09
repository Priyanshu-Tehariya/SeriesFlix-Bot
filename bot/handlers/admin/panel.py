from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from bot.database.models.search_log import SearchLog
from bot.database.models.user import User

from bot.filters.admin import IsAdmin
from bot.services.cache_service import CacheService

admin_router = Router(name="admin_panel")
admin_router.message.filter(IsAdmin())
admin_router.callback_query.filter(IsAdmin())


def build_admin_kb() -> InlineKeyboardMarkup:
  return InlineKeyboardMarkup(
      inline_keyboard=[
          [
              InlineKeyboardButton(
                  text="📊 Stats", callback_data="admin_stats"
              ),
              InlineKeyboardButton(
                  text="🔥 Top Searches", callback_data="admin_top_searches"
              ),
          ],
          [
              InlineKeyboardButton(
                  text="🧹 Flush Cache", callback_data="admin_flush_cache"
              ),
          ],
          [InlineKeyboardButton(text="❌ Close", callback_data="admin_close")],
      ]
  )


@admin_router.message(Command("admin"))
async def cmd_admin_panel(message: Message):
  text = (
      "<b>⚙️ Admin Control Panel</b>\n"
      "─────────────────────────\n"
      "Select an option below to inspect metrics or manage the bot:"
  )
  await message.answer(text, reply_markup=build_admin_kb(), parse_mode="HTML")


@admin_router.callback_query(F.data == "admin_close")
async def cb_admin_close(callback: CallbackQuery):
  await callback.message.delete()


@admin_router.callback_query(F.data == "admin_stats")
async def cb_admin_stats(callback: CallbackQuery, session: AsyncSession):
  # Use select_from(User) to avoid missing column attribute errors
  total_users = (
      await session.execute(select(func.count()).select_from(User))
  ).scalar_one_or_none() or 0

  total_searches = (
      await session.execute(select(func.count()).select_from(SearchLog))
  ).scalar_one_or_none() or 0

  text = (
      "<b>📊 System Statistics</b>\n"
      "─────────────────────────\n"
      f"<b>Total Registered Users:</b> {total_users}\n"
      f"<b>Total Searches Logged:</b> {total_searches}\n"
  )
  await callback.message.edit_text(
      text, reply_markup=build_admin_kb(), parse_mode="HTML"
  )
  await callback.answer()


@admin_router.callback_query(F.data == "admin_top_searches")
async def cb_admin_top_searches(
    callback: CallbackQuery, session: AsyncSession
):
  stmt = (
      select(SearchLog.query_text, func.count(SearchLog.id).label("cnt"))
      .group_by(SearchLog.query_text)
      .order_by(func.count(SearchLog.id).desc())
      .limit(10)
  )
  results = (await session.execute(stmt)).all()

  if not results:
    top_text = "No search history recorded yet."
  else:
    top_text = "\n".join([
        f"{i+1}. <code>{row[0]}</code> — {row[1]} searches"
        for i, row in enumerate(results)
    ])

  text = f"<b>🔥 Top 10 Searches</b>\n─────────────────────────\n{top_text}"
  await callback.message.edit_text(
      text, reply_markup=build_admin_kb(), parse_mode="HTML"
  )
  await callback.answer()


@admin_router.callback_query(F.data == "admin_flush_cache")
async def cb_admin_flush_cache(callback: CallbackQuery, redis):
  # Flush search and meta keys from Redis
  keys = await redis.keys("search:*") + await redis.keys("meta:*")
  if keys:
    await redis.delete(*keys)
  await callback.answer("🧹 Redis cache flushed successfully!", show_alert=True)