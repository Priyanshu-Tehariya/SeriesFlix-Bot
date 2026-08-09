from __future__ import annotations

from aiogram import Router
from aiogram.enums import ChatType
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

from bot.filters.chat_type import ChatTypeFilter
from bot.utils.i18n import t

router = Router(name="user_start")
router.message.filter(ChatTypeFilter(ChatType.PRIVATE))


DIVIDER = "<b>─────────────────────────</b>"

@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    text = (
        "👋 <b>Welcome to SeriesFlix!</b>\n"
        f"{DIVIDER}\n"
        "📺 <b>Note:</b> This bot is strictly for <b>TV Series</b> (movies are"
        " not supported).\n\n"
        "🔍 <b>Send me any series name</b> directly in chat to search.\n"
        "📩 Use /request to ask for a series that isn't available yet.\n"
        "❓ Type /help to view all available commands."
    )
    await message.answer(text, parse_mode="HTML")


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    text = (
        "<b>ℹ️ SeriesFlix Command Guide</b>\n"
        f"{DIVIDER}\n"
        "<b>🔥 Discovery & Search</b>\n"
        "• /trending - View today's top trending TV shows\n"
        "• /popular - Explore the most popular TV shows\n"
        "• Just type any title directly in chat to search!\n\n"
        "<b>🔔 Tracking & Management</b>\n"
        "• /watchlist or /tracked - View all your tracked series\n"
        "• /request - Request a TV series that isn't uploaded yet\n"
        "• /help - Display this command list"
    )
    await message.answer(text, parse_mode="HTML")
