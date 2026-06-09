"""Unified mentions table — every platform lands here with the same shape
(architecture rule 2)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# Allowed enum-like string values (kept as plain strings for a unified, flexible shape).
PLATFORMS = ("ig", "fb", "x")
SOURCE_TYPES = ("comment", "post", "mention", "dm_meta")
SENTIMENT_LABELS = ("positive", "negative", "neutral")


class Mention(Base):
    __tablename__ = "mentions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    politician_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    platform: Mapped[str] = mapped_column(String(8), nullable=False)
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)
    # Stable id from the source platform — used to dedupe on re-ingestion (rule 2).
    platform_mention_id: Mapped[str | None] = mapped_column(String(200))

    raw_text: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(String(16))
    sentiment_score: Mapped[float | None] = mapped_column(Float)  # -1..1
    sentiment_label: Mapped[str | None] = mapped_column(String(16))
    topics: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)

    inferred_city: Mapped[str | None] = mapped_column(String(120))
    inferred_area: Mapped[str | None] = mapped_column(String(120))
    likes_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    platform_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    processed: Mapped[bool] = mapped_column(default=False, nullable=False)

    __table_args__ = (
        # Dedupe: the same source item never lands twice (idempotent ingestion).
        UniqueConstraint(
            "politician_id",
            "platform",
            "platform_mention_id",
            name="uq_mentions_platform_id",
        ),
        # Fast lookups for the per-hour negative-mention spike query.
        Index("ix_mentions_pol_label_ts", "politician_id", "sentiment_label", "platform_ts"),
        Index("ix_mentions_pol_processed", "politician_id", "processed"),
    )
