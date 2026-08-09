from __future__ import annotations

# ---------------------------------------------------------------------------
# Simple dictionary-based translation loader.
# Add new locales by adding keys to TRANSLATIONS.
# ---------------------------------------------------------------------------

TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        "welcome": (
            "👋 <b>Welcome to TV Series Bot!</b>\n\n"
            "🔍 Send me a series name to search.\n"
            "📥 Use /request to request a series that isn't available yet."
        ),
        "help": (
            "📖 <b>How to use:</b>\n\n"
            "• Type any series name to search\n"
            "• Tap a season to pick quality\n"
            "• Tap a quality to see episodes\n"
            "• Tap an episode to download\n\n"
            "Commands:\n"
            "/start — Welcome message\n"
            "/help — This message\n"
            "/request — Request a missing series"
        ),
        "search_no_results": "❌ No results found for <b>{query}</b>.\nTry /request to ask for it.",
        "search_results": "🔍 Results for <b>{query}</b>:",
        "banned": "🚫 You have been banned from using this bot.",
        "throttled": "⏳ You're going too fast! Please wait a moment.",
        "request_prompt": "📝 Please enter the name of the series you want to request:",
        "request_submitted": "✅ Your request for <b>{query}</b> has been submitted!",
        "request_duplicate": "ℹ️ You already have a pending request.",
        "select_season": "📺 <b>{series}</b>\n\nSelect a season:",
        "select_quality": "🎬 <b>{series}</b> — Season {season}\n\nSelect quality:",
        "select_episode": "📺 <b>{series}</b> — S{season:02d} [{quality}]\n\nSelect an episode:",
        "no_episodes": "😢 No episodes available for this quality yet.",
        "delivering": "📤 Sending <b>{title}</b>...",
        "admin_request_card": (
            "📥 <b>New Request</b>\n\n"
            "User: <a href='tg://user?id={user_id}'>{full_name}</a>\n"
            "Query: <b>{query}</b>\n"
            "Status: <b>PENDING</b>"
        ),
        "admin_banned_user": "🚫 User {user_id} has been banned.",
        "admin_unbanned_user": "✅ User {user_id} has been unbanned.",
    }
}

DEFAULT_LOCALE = "en"


def t(key: str, locale: str = DEFAULT_LOCALE, **kwargs: object) -> str:
    """Translate a key to the given locale with optional format substitution."""
    locale_dict = TRANSLATIONS.get(locale, TRANSLATIONS[DEFAULT_LOCALE])
    template = locale_dict.get(key, TRANSLATIONS[DEFAULT_LOCALE].get(key, key))
    if kwargs:
        return template.format(**kwargs)
    return template
