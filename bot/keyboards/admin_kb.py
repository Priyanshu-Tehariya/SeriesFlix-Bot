from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.keyboards.callback_factories import AdminReqCB


def build_request_moderation_kb(request_id: int) -> InlineKeyboardMarkup:
    """
    Builds the admin moderation keyboard for a /request card.
    Three buttons: Uploaded | Coming Soon | Reject
    """
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✅ Uploaded",
        callback_data=AdminReqCB(action="uploaded", request_id=request_id),
    )
    builder.button(
        text="🔜 Coming Soon",
        callback_data=AdminReqCB(action="coming_soon", request_id=request_id),
    )
    builder.button(
        text="❌ Reject",
        callback_data=AdminReqCB(action="reject", request_id=request_id),
    )
    builder.adjust(3)
    return builder.as_markup()
