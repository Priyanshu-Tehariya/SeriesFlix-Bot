from __future__ import annotations

import structlog
from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.database.repositories.user_repo import UserRepository
from bot.filters.admin import IsAdmin

logger = structlog.get_logger(__name__)
router = Router(name="admin_ban")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


@router.message(Command("ban"))
async def cmd_ban(message: Message, command: CommandObject, session: AsyncSession) -> None:
    """
    /ban <user_id> [reason]
    """

    if not command.args:
        await message.answer("<b>Usage:</b> <code>/ban &lt;user_id&gt; [reason]</code>", parse_mode="HTML")
        return

    parts = command.args.split(maxsplit=1)
    user_id_str = parts[0]
    reason = parts[1] if len(parts) > 1 else None

    if not user_id_str.lstrip("-").isdigit():
        await message.answer("⚠️ Invalid user ID.")
        return

    user_id = int(user_id_str)
    
    # Don't let admins ban other admins
    if user_id in settings.ADMIN_IDS:
        await message.answer("⚠️ You cannot ban an administrator.")
        return

    user_repo = UserRepository(session)
    user = await user_repo.get_by_id(user_id)
    if not user:
        await message.answer("⚠️ User not found in database.")
        return

    if user.is_banned:
        await message.answer("⚠️ User is already banned.")
        return

    await user_repo.set_banned(user_id=user_id, is_banned=True, ban_reason=reason)
    await session.commit()

    # 1. Ban Card Message Text
    ban_card_text = (
        f"🚫 *Account Suspended*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"You have been banned from using this bot.\n\n"
        f"📝 *Reason:* {reason or 'No specific reason provided.'}"
    )

    # 2. DM delivery check
    dm_sent = False
    try:
        await message.bot.send_message(
            chat_id=user_id,
            text=ban_card_text,
            parse_mode="Markdown"
        )
        dm_sent = True
    except Exception as e:
        logger.warning(f"Could not send ban PM to {user_id}: {e}")

    # 3. Feedback to Admin
    await message.answer(
        f"🚫 User `{user_id}` banned in database.\n"
        f"{'✅ Ban card sent to user PM.' if dm_sent else '⚠️ Ban saved, but could not DM user (User must start bot in PM first).'}",
        parse_mode="Markdown",
    )


@router.message(Command("unban"))
async def cmd_unban(message: Message, command: CommandObject, session: AsyncSession) -> None:
    """
    /unban <user_id>
    """

    if not command.args:
        await message.answer("<b>Usage:</b> <code>/unban &lt;user_id&gt;</code>", parse_mode="HTML")
        return

    user_id_str = command.args.strip()
    if not user_id_str.lstrip("-").isdigit():
        await message.answer("⚠️ Invalid user ID.")
        return

    user_id = int(user_id_str)
    
    user_repo = UserRepository(session)
    user = await user_repo.get_by_id(user_id)
    if not user:
        await message.answer("⚠️ User not found in database.")
        return

    if not user.is_banned:
        await message.answer("⚠️ User is not currently banned.")
        return

    await user_repo.set_banned(user_id=user_id, is_banned=False, ban_reason=None)
    await session.commit()

    # Attempt to send notification card to the unbanned user
    unban_card = (
        "✅ *Account Restored*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Your ban has been lifted. You can now use the bot again!"
    )
    try:
        if message.bot:
            await message.bot.send_message(chat_id=user_id, text=unban_card, parse_mode="Markdown")
        notified = True
    except Exception as e:
        logger.warning(f"Failed to notify unbanned user {user_id}: {e}")
        notified = False

    notify_text = " (User notified)" if notified else " (Failed to notify user)"
    await message.answer(
        f"✅ User `{user_id}` has been successfully **unbanned**.{notify_text}",
        parse_mode="Markdown"
    )


@router.message(Command("banned"))
async def cmd_banned(message: Message, session: AsyncSession) -> None:
    """
    /banned - Lists currently banned users.
    """

    user_repo = UserRepository(session)
    banned_users = await user_repo.get_banned_users()

    if not banned_users:
        await message.answer("There are currently no banned users.")
        return

    text = "🚫 *Banned Users*\n━━━━━━━━━━━━━━━━━━━━━━\n"
    for user in banned_users:
        reason = f" - {user.ban_reason}" if user.ban_reason else ""
        text += f"• `{user.user_id}` ({user.full_name}){reason}\n"
    
    # Simple truncate if too long
    if len(text) > 4000:
        text = text[:4000] + "...\n(Truncated)"

    await message.answer(text, parse_mode="Markdown")
