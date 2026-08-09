from __future__ import annotations

import enum

from sqlalchemy import BigInteger, Boolean, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.database.base import Base
from bot.database.models.mixins import TimestampMixin


class QualityEnum(str, enum.Enum):
    Q480P = "480p"
    Q720P = "720p"
    Q1080P = "1080p"
    Q1440P = "1440p"
    Q4K = "4K"
    SOURCE_UNKNOWN = "Unknown"


class Episode(Base, TimestampMixin):
    """
    One row = one *deliverable file variant* (== FileRecord).
    A logical episode (e.g. S01E05) can therefore have several rows:
    one per quality/language combination.
    episode_number == 0 is reserved for 'Complete Season Zip' entries.
    """

    __tablename__ = "episodes"
    __table_args__ = (
        UniqueConstraint(
            "season_id", "episode_number", "quality", "language",
            name="uq_episode_variant",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(
        ForeignKey("seasons.id", ondelete="CASCADE"), index=True
    )
    episode_number: Mapped[int] = mapped_column(Integer, index=True)

    # sha256(file_unique_id) — guarantees idempotent re-indexing
    file_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    file_id: Mapped[str] = mapped_column(String(256))          # send-ready Telegram file_id
    file_unique_id: Mapped[str] = mapped_column(String(128))   # stable cross-bot identifier
    file_size: Mapped[int] = mapped_column(BigInteger, default=0)
    raw_filename: Mapped[str] = mapped_column(String(512), default="Unknown")

    quality: Mapped[QualityEnum] = mapped_column(Enum(QualityEnum), index=True)
    language: Mapped[str] = mapped_column(String(64), default="Unknown")

    download_count: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    season: Mapped["Season"] = relationship(back_populates="episodes")
