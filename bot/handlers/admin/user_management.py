from __future__ import annotations

import structlog
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models.banned_user import BannedUser
from bot.database.repositories.user_repo import UserRepository
from bot.filters.admin import IsAdmin
from bot.services.admin_log_service import AdminLogService

logger = structlog.get_logger(__name__)

router = Router(name="admin_user_management")
router.message.filter(IsAdmin())


@router.message(Command("ban"))
async def cmd_ban(message: Message, session: AsyncSession) -> None:
    """
    /ban <user_id> [reason]
    Bans a user and appends an entry to the BannedUser audit log.
    """
    if message.text is None or message.from_user is None:
        return

    parts = message.text.split(maxsplit=2)
    if len(parts) < 2:
        await message.answer("<b>Usage:</b> <code>/ban &lt;user_id&gt; [reason]</code>", parse_mode="HTML")
        return

    try:
        target_id = int(parts[1])
    except ValueError:
        await message.answer("Invalid user_id.")
        return

    reason = parts[2] if len(parts) > 2 else None

    user_repo = UserRepository(session)
    await user_repo.set_banned(target_id, is_banned=True)

    # Append audit log entry
    audit = BannedUser(
        user_id=target_id,
        reason=reason,
        banned_by=message.from_user.id,
    )
    session.add(audit)

    # Log to admin channel
    admin_log = AdminLogService(message.bot)  # type: ignore[arg-type]
    await admin_log.log_ban(message.from_user.id, target_id, reason)

    await message.answer(f"🚫 User <code>{target_id}</code> has been banned.", parse_mode="HTML")


@router.message(Command("unban"))
async def cmd_unban(message: Message, session: AsyncSession) -> None:
    """/unban <user_id>"""
    if message.text is None:
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("<b>Usage:</b> <code>/unban &lt;user_id&gt;</code>", parse_mode="HTML")
        return

    try:
        target_id = int(parts[1])
    except ValueError:
        await message.answer("Invalid user_id.")
        return

    user_repo = UserRepository(session)
    await user_repo.set_banned(target_id, is_banned=False)
    await message.answer(f"✅ User <code>{target_id}</code> has been unbanned.", parse_mode="HTML")


@router.message(Command("stats"))
async def cmd_stats(message: Message, session: AsyncSession) -> None:
    """/stats — Show basic bot statistics."""
    from bot.database.repositories.series_repo import SeriesRepository

    user_repo = UserRepository(session)
    series_repo = SeriesRepository(session)

    total_users = await user_repo.get_total_users()
    total_series = await series_repo.get_total_series()

    text = (
        f"📊 <b>Bot Statistics</b>\n\n"
        f"👤 Total users: <b>{total_users}</b>\n"
        f"📺 Total series: <b>{total_series}</b>"
    )
    await message.answer(text, parse_mode="HTML")
