"""Per-post engagement + reaction breakdown captured by the ingestion worker."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PostMetric(Base):
    __tablename__ = "post_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    politician_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    platform: Mapped[str] = mapped_column(String(8), nullable=False)
    post_id: Mapped[str] = mapped_column(String(120), nullable=False)

    reach: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    impressions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    likes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    comments_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    shares: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    saves: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Facebook reaction breakdown
    react_like: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    react_love: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    react_angry: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    react_sad: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    react_haha: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    react_wow: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
