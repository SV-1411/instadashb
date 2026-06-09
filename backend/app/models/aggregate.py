"""Pre-computed hourly aggregates — the ONLY thing the dashboard reads
(architecture rule 1). One row per politician per IST hour bucket."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Aggregate(Base):
    __tablename__ = "aggregates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    politician_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    bucket_hour: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    sentiment_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # 0-100
    positive_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    negative_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    neutral_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    top_topics: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    is_spike: Mapped[bool] = mapped_column(default=False, nullable=False)

    __table_args__ = (
        # Idempotency: re-running a cycle upserts the same bucket, never double-counts.
        UniqueConstraint("politician_id", "bucket_hour", name="uq_aggregates_pol_bucket"),
    )
