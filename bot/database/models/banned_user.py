from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from bot.database.base import Base


class BannedUser(Base):
    """Append-only audit trail. Live enforcement reads User.is_banned instead."""

    __tablename__ = "banned_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), index=True
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    banned_by: Mapped[int] = mapped_column(BigInteger)  # admin's Telegram user_id
    banned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
