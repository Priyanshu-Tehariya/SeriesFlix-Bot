from datetime import datetime
from sqlalchemy import BigInteger, Column, DateTime, Integer, UniqueConstraint
from bot.database.base import Base


class TrackedShow(Base):
  __tablename__ = "tracked_shows"

  id = Column(Integer, primary_key=True, autoincrement=True)
  user_id = Column(BigInteger, nullable=False, index=True)
  series_id = Column(Integer, nullable=False, index=True)
  created_at = Column(DateTime, default=datetime.utcnow)

  __table_args__ = (
      UniqueConstraint("user_id", "series_id", name="uix_user_series_track"),
  )
