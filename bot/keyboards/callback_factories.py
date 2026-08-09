from aiogram.filters.callback_data import CallbackData


class SeasonCB(CallbackData, prefix="szn"):
    """Series page -> tap a season button."""
    series_id: int
    season_id: int


class QualityCB(CallbackData, prefix="qty"):
    """Season page -> tap a quality/variant button."""
    season_id: int
    quality: str   # "480p" | "720p" | "1080p" | "4K" | "ZIP"


class EpisodeCB(CallbackData, prefix="ep"):
    """Quality page -> tap an episode cell in the grid."""
    season_id: int
    episode_id: int


class BatchDownloadCB(CallbackData, prefix="batch"):
    """Quality page -> batch download all episodes."""
    season_id: int
    quality: str


class NavCB(CallbackData, prefix="nav"):
    """Back-navigation / close actions shared across all steps."""
    action: str    # "to_seasons" | "to_qualities" | "close"
    target_id: int  # series_id or season_id, depending on action


class AdminReqCB(CallbackData, prefix="areq"):
    """Admin moderation buttons on a /request card."""
    action: str    # "uploaded" | "coming_soon" | "reject"
    request_id: int


class AdminDeleteFileCB(CallbackData, prefix="delfile"):
    """Admin button to delete a file directly from the index log card or manage message."""
    episode_id: int
    source: str = "log"


class VerifyFSubCB(CallbackData, prefix="fsub"):
    """Verify subscription button in the FSub card."""
    action: str = "verify"


class RequestActionCB(CallbackData, prefix="req_act"):
    action: str  # "uploaded", "coming_soon", "unavailable"
    user_id: int
    title: str
