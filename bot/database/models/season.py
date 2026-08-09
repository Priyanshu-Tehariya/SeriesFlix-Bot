from __future__ import annotations

from typing import List

from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.database.base import Base


class Season(Base):
    __tablename__ = "seasons"
    __table_args__ = (
        UniqueConstraint("series_id", "season_number", name="uq_series_season_number"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    series_id: Mapped[int] = mapped_column(
        ForeignKey("series.id", ondelete="CASCADE"), index=True
    )
    season_number: Mapped[int] = mapped_column(Integer)

    series: Mapped["Series"] = relationship(back_populates="seasons")
    episodes: Mapped[List["Episode"]] = relationship(
        back_populates="season",
        cascade="all, delete-orphan",
        order_by="Episode.episode_number",
        lazy="selectin",
    )
