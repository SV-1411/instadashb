"""Daily audience geography snapshot (city-level only — Meta gives no finer)."""

from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AudienceGeo(Base):
    __tablename__ = "audience_geo"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    politician_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)

    city: Mapped[str | None] = mapped_column(String(120))
    follower_pct: Mapped[float | None] = mapped_column(Float)
    age_band: Mapped[str | None] = mapped_column(String(20))
    gender: Mapped[str | None] = mapped_column(String(16))
