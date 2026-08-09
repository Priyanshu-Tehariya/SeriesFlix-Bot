# Re-export all models here so that Alembic's autogenerate can discover them
# via: from bot.database.models import *
from bot.database.models.banned_user import BannedUser
from bot.database.models.episode import Episode, QualityEnum
from bot.database.models.file_request import FileRequest, RequestStatus
from bot.database.models.mixins import TimestampMixin
from bot.database.models.search_log import SearchLog
from bot.database.models.season import Season
from bot.database.models.series import Series
from bot.database.models.user import User
from bot.database.models.tracked_show import TrackedShow

__all__ = [
    "User",
    "Series",
    "Season",
    "Episode",
    "QualityEnum",
    "FileRequest",
    "RequestStatus",
    "BannedUser",
    "SearchLog",
    "TimestampMixin",
    "TrackedShow",
]
