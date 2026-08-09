from __future__ import annotations

from typing import List

from sqlalchemy import Float, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.database.base import Base
from bot.database.models.mixins import TimestampMixin


class Series(Base, TimestampMixin):
    __tablename__ = "series"
    __table_args__ = (
        Index("ix_series_normalized_title", "normalized_title"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(512))
    # Lowercased, punctuation-stripped title — used for exact/prefix lookups & cache keys
    normalized_title: Mapped[str] = mapped_column(String(512), unique=True)
    poster_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    seasons: Mapped[List["Season"]] = relationship(
        back_populates="series",
        cascade="all, delete-orphan",
        order_by="Season.season_number",
        lazy="selectin",
    )
