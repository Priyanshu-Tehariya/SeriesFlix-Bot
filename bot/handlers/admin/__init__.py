from bot.handlers.admin.content import router as content_router
from bot.handlers.admin.moderation import router as moderation_router
from bot.handlers.admin.user_management import router as user_management_router
from bot.handlers.admin.broadcast import router as broadcast_router

__all__ = ["content_router", "moderation_router", "user_management_router", "broadcast_router"]
