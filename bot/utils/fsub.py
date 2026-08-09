from __future__ import annotations

import structlog
from aiogram import Bot
from bot.config import settings

logger = structlog.get_logger(__name__)


async def get_channel_invite_link(bot: Bot, channel_id: int | str, index: int = 0) -> str:
    """
    Dynamically resolve an invite link for a given channel ID or username.
    Tries settings.FORCE_SUB_LINKS[index] first, then public username, then dynamic generation.
    """
    # 1. First check if a explicit link was provided in FORCE_SUB_LINKS at the corresponding index
    if index < len(settings.FORCE_SUB_LINKS) and settings.FORCE_SUB_LINKS[index]:
        return settings.FORCE_SUB_LINKS[index]

    # 2. For public usernames (e.g. @MyChannel)
    if isinstance(channel_id, str) and channel_id.startswith("@"):
        return f"https://t.me/{channel_id.lstrip('@')}"

    # 3. Dynamic fallback attempt via bot API
    try:
        chat = await bot.get_chat(channel_id)
        if chat.invite_link:
            return chat.invite_link
        invite = await bot.create_chat_invite_link(channel_id)
        return invite.invite_link
    except Exception as e:
        logger.error(f"Failed to generate invite link for {channel_id}: {e}")
        return "https://t.me"
