from __future__ import annotations

import structlog
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware, Bot
from aiogram.types import Message, CallbackQuery, TelegramObject

from bot.config import settings
from bot.keyboards.callback_factories import VerifyFSubCB

logger = structlog.get_logger(__name__)


class ForceSubMiddleware(BaseMiddleware):
    """
    Checks if a user is subscribed to all FORCE_SUB_CHANNELS before processing their request.
    Exempts ADMIN_IDS, /start, /help, /request, and VerifyFSubCB callbacks.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        
        user = None
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user
            
        if not user:
            return await handler(event, data)

        # 1. Bypass check if user is an admin
        if user.id in settings.ADMIN_IDS:
            return await handler(event, data)
            
        # 2. Bypass check if no channels are configured
        if not settings.FORCE_SUB_CHANNELS:
            return await handler(event, data)
            
        # 3. Bypass exemptions (commands or verification callback)
        if isinstance(event, Message) and event.text:
            text = event.text
            if text.startswith("/start") or text.startswith("/help") or text.startswith("/request"):
                return await handler(event, data)
                
        if isinstance(event, CallbackQuery) and event.data:
            try:
                cb = VerifyFSubCB.unpack(event.data)
                return await handler(event, data)
            except (ValueError, TypeError):
                pass
                
        # 4. Check membership for each channel
        bot: Bot = data["bot"]
        is_subscribed = True
        
        for channel in settings.FORCE_SUB_CHANNELS:
            try:
                member = await bot.get_chat_member(chat_id=channel, user_id=user.id)
                if member.status not in ["creator", "administrator", "member"]:
                    is_subscribed = False
                    break
            except Exception as e:
                logger.warning("fsub_check_failed", channel=channel, user_id=user.id, error=str(e))
                # If bot is not in the channel or user doesn't exist, assume they are not subscribed
                is_subscribed = False
                break
                
        # 5. If fully subscribed, proceed
        if is_subscribed:
            return await handler(event, data)
            
        # 6. User is not subscribed -> Prompt them
        from bot.keyboards.inline.fsub_kb import build_fsub_kb
        
        state = data.get("state")
        if state and isinstance(event, Message) and event.text and not event.text.startswith("/"):
            await state.update_data(pending_search=event.text.strip())
        
        # Build dynamic FSub keyboard with links
        kb = await build_fsub_kb(bot, settings.FORCE_SUB_CHANNELS)
        
        caption = (
            "📢 <b>Channel Subscription Required</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "You must join our official channel(s) to search and download series files.\n\n"
            "Please join below and click <b>Verify Subscription</b> to continue!"
        )
        
        if isinstance(event, CallbackQuery):
            if event.message:
                from bot.handlers.user.navigation import smart_edit_message
                await smart_edit_message(
                    message=event.message,
                    text=caption,
                    reply_markup=kb,
                )
            await event.answer("Subscription required!", show_alert=True)
        elif isinstance(event, Message):
            await event.answer(caption, reply_markup=kb, parse_mode="HTML")
            
        # Stop processing handler
        return None
