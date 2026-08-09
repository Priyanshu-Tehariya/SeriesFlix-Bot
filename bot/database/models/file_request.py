from __future__ import annotations

import enum

from sqlalchemy import BigInteger, Enum, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.database.base import Base
from bot.database.models.mixins import TimestampMixin


class RequestStatus(str, enum.Enum):
    PENDING = "pending"
    UPLOADED = "uploaded"
    COMING_SOON = "coming_soon"
    REJECTED = "rejected"


class FileRequest(Base, TimestampMixin):
    __tablename__ = "file_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), index=True
    )
    query_text: Mapped[str] = mapped_column(Text)
    status: Mapped[RequestStatus] = mapped_column(
        Enum(RequestStatus), default=RequestStatus.PENDING, index=True
    )
    # Message ID of the moderation card posted in the Admin channel, so callback
    # handlers can edit it in place when an admin acts on the request.
    admin_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    user: Mapped["User"] = relationship(back_populates="requests")
