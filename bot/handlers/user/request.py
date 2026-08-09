from __future__ import annotations

from aiogram import Router
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.filters.chat_type import ChatTypeFilter
from bot.services.request_service import RequestService
from bot.states.request_states import RequestFSM
from bot.utils.i18n import t

router = Router(name="user_request")
router.message.filter(ChatTypeFilter(ChatType.PRIVATE))


@router.message(Command("request"))
async def cmd_request(message: Message, state: FSMContext, session: AsyncSession) -> None:
    """
    /request <query> — inline mode.
    /request (no args) — enters FSM to capture query text.
    """
    if message.text is None:
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) > 1:
        # Inline: /request Game of Thrones
        query = parts[1].strip()
        await _submit_request(message, query, session)
    else:
        # FSM: prompt user for the query
        await state.set_state(RequestFSM.waiting_for_query)
        await message.answer(t("request_prompt"), parse_mode="HTML")


@router.message(RequestFSM.waiting_for_query)
async def handle_request_query(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    await state.clear()
    if message.text is None:
        return
    query = message.text.strip()
    if not query:
        await message.answer("Please enter a valid series name.")
        return
    await _submit_request(message, query, session)


async def _submit_request(
    message: Message,
    query: str,
    session: AsyncSession,
) -> None:
    if message.from_user is None:
        return

    svc = RequestService(session, message.bot)  # type: ignore[arg-type]
    await svc.create_request(
        user_id=message.from_user.id,
        query_text=query,
        full_name=message.from_user.full_name,
        username=message.from_user.username,
    )
    await message.answer(t("request_submitted", query=query), parse_mode="HTML")
