from __future__ import annotations

from aiogram import Dispatcher

from bot.handlers.user.start import router as start_router
from bot.handlers.user.search import router as search_router
from bot.handlers.user.navigation import router as navigation_router
from bot.handlers.user.request import router as request_router
from bot.handlers.user.discovery import discovery_router
from bot.handlers.user.tracking import tracking_router
from bot.handlers.user.fsub import router as fsub_router
from bot.handlers.channel.auto_index import router as auto_index_router
from bot.handlers.admin.content import router as content_router
from bot.handlers.admin.moderation import router as moderation_router
from bot.handlers.admin.user_management import router as user_management_router
from bot.handlers.admin.broadcast import router as broadcast_router
from bot.handlers.admin.panel import admin_router as admin_panel_router
from bot.handlers.admin.ban import router as ban_router


def register_all_routers(dp: Dispatcher) -> None:
    """Register all routers in priority order."""
    # Admin routers first (higher priority)
    dp.include_router(admin_panel_router)
    dp.include_router(content_router)
    dp.include_router(moderation_router)
    dp.include_router(user_management_router)
    dp.include_router(broadcast_router)
    dp.include_router(ban_router)

    # Channel indexing
    dp.include_router(auto_index_router)

    # User routers (start, navigation, request, search — search last as catch-all)
    dp.include_router(start_router)
    dp.include_router(discovery_router)
    dp.include_router(tracking_router)
    dp.include_router(fsub_router)
    dp.include_router(navigation_router)
    dp.include_router(request_router)
    dp.include_router(search_router)  # catch-all text handler must be last
