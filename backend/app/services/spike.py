"""Spike detection + push (WP5) — the product's core job.

Rule (constitution): a bucket spikes when
    current_hour_negative > max(7day_hourly_avg_negative * SPIKE_MULTIPLIER, SPIKE_MIN_ABSOLUTE)

On a spike we fire EXACTLY ONE FCM push per spike event. Dedupe is persistent and
crash-safe: the push only fires on the transition from is_spike=False -> True, and
the flag is stored on the aggregate row, so re-running a cycle never re-pushes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.clients.fcm import FcmClient, PushMessage
from app.config import get_settings
from app.core.logging import get_logger
from app.core.timezone import floor_to_hour_ist
from app.models.mention import Mention
from app.services.aggregate import upsert_aggregate

log = get_logger("services.spike")


@dataclass
class SpikeResult:
    politician_id: int
    bucket_hour: datetime
    current_negative: int
    baseline_avg: float
    threshold: float
    spiked: bool
    push_fired: bool


def seven_day_hourly_avg_negative(db: Session, politician_id: int, bucket_hour: datetime) -> float:
    """Average negative mentions per hour over the 7 days before this bucket."""
    start = bucket_hour - timedelta(days=7)
    total = db.execute(
        select(func.count(Mention.id)).where(
            Mention.politician_id == politician_id,
            Mention.sentiment_label == "negative",
            Mention.platform_ts >= start,
            Mention.platform_ts < bucket_hour,
        )
    ).scalar_one()
    return total / (7 * 24)


def detect_spike(
    db: Session, fcm: FcmClient, politician_id: int, bucket_hour: datetime
) -> SpikeResult:
    """Evaluate one bucket; fire at most one push on a fresh spike."""
    settings = get_settings()
    bucket_hour = floor_to_hour_ist(bucket_hour)

    # Ensure the aggregate (with negative_count + is_spike) exists and is current.
    agg = upsert_aggregate(db, politician_id, bucket_hour)

    current_negative = agg.negative_count
    baseline_avg = seven_day_hourly_avg_negative(db, politician_id, bucket_hour)
    threshold = max(baseline_avg * settings.spike_multiplier, float(settings.spike_min_absolute))

    spiking = current_negative > threshold
    push_fired = False

    if spiking and not agg.is_spike:
        # Transition into spike -> mark + fire exactly one push.
        agg.is_spike = True
        db.commit()
        fcm.send(
            PushMessage(
                politician_id=politician_id,
                title="⚠️ Negative sentiment spike",
                body=(
                    f"{current_negative} negative mentions this hour "
                    f"(baseline ~{baseline_avg:.1f}/hr). Tap to review Crisis & DMs."
                ),
                dedupe_key=f"spike:{politician_id}:{bucket_hour.isoformat()}",
            )
        )
        push_fired = True
        log.info(
            "spike_detected",
            politician_id=politician_id,
            current_negative=current_negative,
            threshold=round(threshold, 2),
        )

    return SpikeResult(
        politician_id=politician_id,
        bucket_hour=bucket_hour,
        current_negative=current_negative,
        baseline_avg=baseline_avg,
        threshold=threshold,
        spiked=spiking,
        push_fired=push_fired,
    )
