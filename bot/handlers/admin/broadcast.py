from __future__ import annotations

import asyncio
import structlog
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.repositories.user_repo import UserRepository
from bot.filters.admin import IsAdmin

logger = structlog.get_logger(__name__)

router = Router(name="admin_broadcast")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())

from bot.config import settings
from aiogram.fsm.context import FSMContext
from bot.services.broadcast_service import BroadcastService
from bot.states.admin_states import BroadcastFSM


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, state: FSMContext):

    # 1. Capture user's /broadcast command ID
    cmd_id = message.message_id

    # 2. If command is a reply to a message, capture replied message ID
    if message.reply_to_message:
        target_msg = message.reply_to_message
        status_msg = await message.answer("📡 Starting broadcast...")
        # Fire background task with explicit IDs
        asyncio.create_task(
            BroadcastService.run_broadcast(
                bot=message.bot,
                admin_chat_id=message.chat.id,
                broadcast_msg=target_msg,
                status_msg=status_msg,
                cleanup_ids=[cmd_id, target_msg.message_id],
            )
        )
        return

    # 3. If no reply, ask for prompt and track IDs in FSM
    prompt_msg = await message.answer(
        "Please send the message (text, photo, video, etc.) you want to broadcast.\nOr type /cancel to abort."
    )
    await state.update_data(
        cleanup_ids=[cmd_id, prompt_msg.message_id],
        prompt_id=prompt_msg.message_id,
    )
    await state.set_state(BroadcastFSM.waiting_for_message)


@router.message(BroadcastFSM.waiting_for_message)
async def process_broadcast_message(message: Message, state: FSMContext):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("Broadcast cancelled.")
        return

    data = await state.get_data()
    cleanup_ids = data.get("cleanup_ids", [])

    # Append the broadcast input message ID (e.g., "Test")
    cleanup_ids.append(message.message_id)
    await state.clear()

    status_msg = await message.answer("📡 Starting broadcast...")

    asyncio.create_task(
        BroadcastService.run_broadcast(
            bot=message.bot,
            admin_chat_id=message.chat.id,
            broadcast_msg=message,
            status_msg=status_msg,
            cleanup_ids=cleanup_ids,
        )
    )
