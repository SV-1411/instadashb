"""⭐ CROWN-JEWEL TEST (constitution: single most important test).

Insert a burst of negative mentions in the current hour on top of a low 7-day
baseline, run ONE detection cycle, and assert that a spike is detected and EXACTLY
ONE FCM push fires. Re-running must NOT fire a second push (dedupe). No live APIs.
"""

from __future__ import annotations

from datetime import timedelta

from app.clients.fcm import FakeFcmClient
from app.core.timezone import floor_to_hour_ist, now_ist
from app.models.aggregate import Aggregate
from app.models.mention import Mention
from app.models.politician import Politician
from app.services.spike import detect_spike
from sqlalchemy.orm import Session


def _add_negative(db: Session, pol_id: int, tag: str, when) -> None:  # type: ignore[no-untyped-def]
    db.add(
        Mention(
            politician_id=pol_id,
            platform="fb",
            source_type="comment",
            platform_mention_id=tag,
            raw_text="corruption shame",
            language="en",
            sentiment_score=-0.9,
            sentiment_label="negative",
            topics=[],
            likes_count=0,
            platform_ts=when,
            processed=True,
        )
    )


def test_spike_fires_exactly_one_push_then_dedupes(db_session: Session) -> None:
    pol = Politician(name="Spike Demo")
    db_session.add(pol)
    db_session.commit()
    db_session.refresh(pol)

    now = floor_to_hour_ist(now_ist())

    # Low baseline: a handful of negatives spread across the previous 7 days.
    for d in range(1, 8):
        _add_negative(db_session, pol.id, f"base_{d}", now - timedelta(days=d, hours=1))
    db_session.commit()

    # Burst: 15 negative mentions in the CURRENT hour.
    for i in range(15):
        _add_negative(db_session, pol.id, f"burst_{i}", now + timedelta(minutes=i % 55))
    db_session.commit()

    fcm = FakeFcmClient()

    # ── One detection cycle ──────────────────────────────────────────────────
    result = detect_spike(db_session, fcm, pol.id, now)
    assert result.spiked is True
    assert result.push_fired is True
    assert result.current_negative == 15
    assert len(fcm.sent) == 1  # exactly ONE push
    assert fcm.sent[0].politician_id == pol.id

    # The aggregate row is marked as a spike.
    agg = db_session.query(Aggregate).filter_by(politician_id=pol.id, bucket_hour=now).one()
    assert agg.is_spike is True

    # ── Re-run: must NOT fire a second push (dedupe) ─────────────────────────
    again = detect_spike(db_session, fcm, pol.id, now)
    assert again.spiked is True
    assert again.push_fired is False
    assert len(fcm.sent) == 1  # still exactly one


def test_no_spike_when_below_threshold(db_session: Session) -> None:
    pol = Politician(name="No Spike Demo")
    db_session.add(pol)
    db_session.commit()
    db_session.refresh(pol)

    now = floor_to_hour_ist(now_ist())
    # Only 2 negatives this hour — below the absolute floor (SPIKE_MIN_ABSOLUTE=5).
    for i in range(2):
        _add_negative(db_session, pol.id, f"low_{i}", now + timedelta(minutes=i))
    db_session.commit()

    fcm = FakeFcmClient()
    result = detect_spike(db_session, fcm, pol.id, now)
    assert result.spiked is False
    assert result.push_fired is False
    assert len(fcm.sent) == 0
