"""IST (Asia/Kolkata) time helpers — all bucketing is IST end-to-end."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def now_ist() -> datetime:
    """Current timezone-aware time in IST."""
    return datetime.now(tz=IST)


def to_ist(dt: datetime) -> datetime:
    """Convert any datetime to IST. Naive datetimes are assumed to be IST."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=IST)
    return dt.astimezone(IST)


def floor_to_hour_ist(dt: datetime) -> datetime:
    """Floor a datetime to the start of its IST hour (used for aggregate buckets)."""
    ist = to_ist(dt)
    return ist.replace(minute=0, second=0, microsecond=0)
