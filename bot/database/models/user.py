from __future__ import annotations

from typing import List

from sqlalchemy import BigInteger, Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.database.base import Base
from bot.database.models.mixins import TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    # Telegram user IDs exceed 32-bit range -> BigInteger, and serves as PK directly (no surrogate id needed)
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    full_name: Mapped[str] = mapped_column(String(256))
    username: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    ban_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    total_requests: Mapped[int] = mapped_column(Integer, default=0)

    requests: Mapped[List["FileRequest"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<User id={self.user_id} username={self.username!r}>"
