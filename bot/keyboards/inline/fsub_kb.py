from __future__ import annotations

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.keyboards.callback_factories import VerifyFSubCB
from bot.utils.fsub import get_channel_invite_link


async def build_fsub_kb(bot: Bot, channels: list[int | str]) -> InlineKeyboardMarkup:
    """Builds the FSub keyboard with dynamic join links for each channel and a verify button."""
    builder = InlineKeyboardBuilder()
    
    for i, channel in enumerate(channels):
        link = await get_channel_invite_link(bot, channel, i)
        builder.button(
            text=f"📢 Join Channel {i+1}" if len(channels) > 1 else "📢 Join Channel",
            url=link
        )
        
    builder.button(
        text="🔄 Verify Subscription",
        callback_data=VerifyFSubCB(action="verify")
    )
    
    builder.adjust(1)
    return builder.as_markup()
