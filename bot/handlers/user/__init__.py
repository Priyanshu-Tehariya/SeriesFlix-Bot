from bot.handlers.user.start import router as start_router
from bot.handlers.user.search import router as search_router
from bot.handlers.user.navigation import router as navigation_router
from bot.handlers.user.request import router as request_router

__all__ = ["start_router", "search_router", "navigation_router", "request_router"]
