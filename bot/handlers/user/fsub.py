from __future__ import annotations

from aiogram import Router
from aiogram.types import CallbackQuery

from aiogram.fsm.context import FSMContext
from bot.keyboards.callback_factories import VerifyFSubCB
from sqlalchemy.ext.asyncio import AsyncSession
from bot.handlers.user.search import perform_search

router = Router(name="user_fsub")


@router.callback_query(VerifyFSubCB.filter())
async def on_verify_fsub(
    callback: CallbackQuery,
    callback_data: VerifyFSubCB,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Handle the Verify Subscription button click.
    If this handler executes, it means the user passed the ForceSubMiddleware check,
    so they are fully subscribed!
    """
    await callback.answer("✅ Subscription verified! Access restored.", show_alert=True)
    
    # Delete the FSub alert card
    if callback.message:
        try:
            await callback.message.delete()
        except Exception:
            pass

    # Check for pending search
    state_data = await state.get_data()
    pending_search = state_data.get("pending_search")
    
    if pending_search and callback.message:
        await state.update_data(pending_search=None)
        await perform_search(
            query=pending_search,
            user_id=callback.from_user.id,
            answer_func=callback.message.answer,
            answer_photo_func=callback.message.answer_photo,
            session=session,
        )
