from __future__ import annotations

import structlog
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models.file_request import RequestStatus
from bot.database.repositories.request_repo import RequestRepository
from bot.database.repositories.user_repo import UserRepository
from bot.keyboards.admin_kb import build_request_moderation_kb
from bot.services.admin_log_service import AdminLogService
from bot.config import settings

logger = structlog.get_logger(__name__)


class RequestService:
    """
    /request lifecycle:
      create → post moderation card to Admin channel → admin acts (uploaded/coming_soon/reject)
      → update status in DB → edit admin card → DM the requester
    """

    def __init__(self, session: AsyncSession, bot: Bot) -> None:
        self._session = session
        self._bot = bot
        self._request_repo = RequestRepository(session)
        self._user_repo = UserRepository(session)
        self._admin_log = AdminLogService(bot)

    async def create_request(self, user_id: int, query_text: str, full_name: str | None = None, username: str | None = None) -> int:
        """Create a FileRequest and post a moderation card to the admin channel. Returns request_id."""
        # Ensure user exists before creating request to avoid ForeignKey violation
        user = await self._user_repo.upsert(user_id=user_id, full_name=full_name or str(user_id), username=username)

        # Increment user's request counter
        await self._user_repo.increment_request_count(user_id)

        req = await self._request_repo.create(user_id=user_id, query_text=query_text)
        
        # Use the guaranteed full_name for the card
        display_name = user.full_name if user.full_name else str(user_id)

        # Post moderation card to Admin channel
        card_text = (
            f"📥 <b>New Request #{req.id}</b>\n\n"
            f"User: <a href='tg://user?id={user_id}'>{display_name}</a>\n"
            f"Query: <b>{query_text}</b>\n"
            f"Status: <b>PENDING</b>"
        )
        kb = build_request_moderation_kb(req.id)

        try:
            sent = await self._bot.send_message(
                chat_id=settings.REQUEST_CHANNEL_ID,
                text=card_text,
                reply_markup=kb,
                parse_mode="HTML",
            )
            await self._request_repo.set_admin_message_id(req.id, sent.message_id)
        except Exception as e:
            logger.error("request_card_send_failed", error=str(e), request_id=req.id)

        return req.id

    async def handle_admin_action(
        self,
        request_id: int,
        action: str,
        admin_id: int,
    ) -> tuple[bool, str]:
        """
        Process admin button press.

        Returns (success, feedback_text_for_requester).
        """
        req = await self._request_repo.get_by_id(request_id)
        if req is None:
            return False, "Request not found."

        match action:
            case "uploaded":
                status = RequestStatus.UPLOADED
                dm_text = (
                    f"✅ Your request for <b>{req.query_text}</b> has been fulfilled! "
                    f"Search for it now."
                )
            case "coming_soon":
                status = RequestStatus.COMING_SOON
                dm_text = (
                    f"🔜 Your request for <b>{req.query_text}</b> is noted. "
                    f"We'll upload it soon!"
                )
            case "reject":
                status = RequestStatus.REJECTED
                dm_text = (
                    f"❌ Your request for <b>{req.query_text}</b> was not approved."
                )
            case _:
                return False, "Unknown action."

        await self._request_repo.update_status(request_id, status)

        # DM the requester
        try:
            await self._bot.send_message(
                chat_id=req.user_id,
                text=dm_text,
                parse_mode="HTML",
            )
        except Exception as e:
            logger.warning("request_dm_failed", error=str(e), user_id=req.user_id)

        return True, dm_text
