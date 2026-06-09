"""IST helper unit tests (no DB needed)."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.timezone import IST, floor_to_hour_ist, now_ist, to_ist


def test_now_ist_is_aware_and_ist() -> None:
    n = now_ist()
    assert n.tzinfo is not None
    assert n.utcoffset() == IST.utcoffset(n)


def test_to_ist_converts_utc() -> None:
    utc_noon = datetime(2026, 6, 9, 12, 0, tzinfo=ZoneInfo("UTC"))
    ist = to_ist(utc_noon)
    # IST is UTC+5:30
    assert (ist.hour, ist.minute) == (17, 30)


def test_floor_to_hour_ist() -> None:
    dt = datetime(2026, 6, 9, 14, 47, 33, tzinfo=IST)
    floored = floor_to_hour_ist(dt)
    assert (floored.hour, floored.minute, floored.second) == (14, 0, 0)
