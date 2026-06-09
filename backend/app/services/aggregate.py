"""Aggregation (WP3): turn raw mentions/metrics into the per-hour `aggregates`
rows the dashboard reads. Implements the constitution's 0-100 score formula and
is idempotent — re-running a bucket updates in place, never double-counts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.timezone import floor_to_hour_ist, now_ist
from app.models.aggregate import Aggregate
from app.models.mention import Mention
from app.models.post_metric import PostMetric
from app.services.sentiment_reactions import reaction_ratio_score

log = get_logger("services.aggregate")

# Score formula weights (constitution): 40% reaction, 40% comment-NLP, 20% engagement-vs-baseline.
W_REACTION = 0.40
W_COMMENT = 0.40
W_ENGAGEMENT = 0.20


@dataclass
class BucketScore:
    score_0_100: int
    positive: int
    negative: int
    neutral: int
    top_topics: list[dict]


def _scale_unit_to_100(unit: float) -> float:
    """Map a -1..1 sentiment to 0..100 (0->0, neutral 0->50, +1->100)."""
    return (unit + 1.0) / 2.0 * 100.0


def _engagement_baseline(db: Session, politician_id: int, before: datetime) -> float | None:
    """Avg engagement-per-post over the 30 days before ``before`` (this politician)."""
    start = before - timedelta(days=30)
    rows = (
        db.execute(
            select(PostMetric).where(
                PostMetric.politician_id == politician_id,
                PostMetric.captured_at >= start,
                PostMetric.captured_at < before,
            )
        )
        .scalars()
        .all()
    )
    if not rows:
        return None
    eng = [pm.likes + pm.comments_count + pm.shares + pm.saves for pm in rows]
    return sum(eng) / len(eng)


def compute_bucket(db: Session, politician_id: int, bucket_hour: datetime) -> BucketScore:
    """Compute the 0-100 score + label counts for one IST hour bucket."""
    nxt = bucket_hour + timedelta(hours=1)

    mentions = (
        db.execute(
            select(Mention).where(
                Mention.politician_id == politician_id,
                Mention.platform_ts >= bucket_hour,
                Mention.platform_ts < nxt,
            )
        )
        .scalars()
        .all()
    )

    positive = sum(1 for m in mentions if m.sentiment_label == "positive")
    negative = sum(1 for m in mentions if m.sentiment_label == "negative")
    neutral = sum(1 for m in mentions if m.sentiment_label == "neutral")

    # Roll up topics seen in this bucket -> [{"topic": t, "count": n}] (top 5).
    topic_counts: dict[str, int] = {}
    for m in mentions:
        for t in m.topics or []:
            topic_counts[t] = topic_counts.get(t, 0) + 1
    top_topics = [
        {"topic": t, "count": c}
        for t, c in sorted(topic_counts.items(), key=lambda kv: kv[1], reverse=True)[:5]
    ]

    # Comment component: mean comment sentiment (-1..1) -> 0..100.
    comment_units = [m.sentiment_score for m in mentions if m.sentiment_score is not None]
    comment_100 = (
        _scale_unit_to_100(sum(comment_units) / len(comment_units)) if comment_units else 50.0
    )

    # Reaction component: mean reaction-ratio over this bucket's post_metrics -> 0..100.
    metrics = (
        db.execute(
            select(PostMetric).where(
                PostMetric.politician_id == politician_id,
                PostMetric.captured_at >= bucket_hour,
                PostMetric.captured_at < nxt,
            )
        )
        .scalars()
        .all()
    )
    if metrics:
        ratios = [
            reaction_ratio_score(
                {
                    "like": pm.react_like,
                    "love": pm.react_love,
                    "haha": pm.react_haha,
                    "wow": pm.react_wow,
                    "sad": pm.react_sad,
                    "angry": pm.react_angry,
                }
            )
            for pm in metrics
        ]
        reaction_100 = _scale_unit_to_100(sum(ratios) / len(ratios))
    else:
        reaction_100 = 50.0

    # Engagement component: this bucket vs the politician's own 30-day baseline.
    baseline = _engagement_baseline(db, politician_id, bucket_hour)
    if baseline and metrics:
        cur = sum(pm.likes + pm.comments_count + pm.shares + pm.saves for pm in metrics) / len(
            metrics
        )
        engagement_100 = max(0.0, min(100.0, (cur / baseline) * 50.0))  # baseline == 50
    else:
        engagement_100 = 50.0  # calibrating

    score = W_REACTION * reaction_100 + W_COMMENT * comment_100 + W_ENGAGEMENT * engagement_100
    return BucketScore(
        score_0_100=int(round(score)),
        positive=positive,
        negative=negative,
        neutral=neutral,
        top_topics=top_topics,
    )


def upsert_aggregate(db: Session, politician_id: int, bucket_hour: datetime) -> Aggregate:
    """Insert or update the aggregate row for a bucket. Preserves is_spike (set by
    the spike service) so recomputation never clears a recorded spike."""
    bucket_hour = floor_to_hour_ist(bucket_hour)
    bs = compute_bucket(db, politician_id, bucket_hour)

    row = db.execute(
        select(Aggregate).where(
            Aggregate.politician_id == politician_id,
            Aggregate.bucket_hour == bucket_hour,
        )
    ).scalar_one_or_none()

    if row is None:
        row = Aggregate(politician_id=politician_id, bucket_hour=bucket_hour, is_spike=False)
        db.add(row)
    row.sentiment_score = bs.score_0_100
    row.positive_count = bs.positive
    row.negative_count = bs.negative
    row.neutral_count = bs.neutral
    row.top_topics = bs.top_topics
    db.commit()
    db.refresh(row)
    return row


def rebuild_recent_aggregates(db: Session, politician_id: int, hours: int = 48) -> int:
    """Rebuild aggregates for every IST hour bucket in the last ``hours`` that has data."""
    since = floor_to_hour_ist(now_ist()) - timedelta(hours=hours)
    buckets = (
        db.execute(
            select(func.date_trunc("hour", Mention.platform_ts))
            .where(Mention.politician_id == politician_id, Mention.platform_ts >= since)
            .distinct()
        )
        .scalars()
        .all()
    )
    count = 0
    for b in buckets:
        if b is None:
            continue
        upsert_aggregate(db, politician_id, b)
        count += 1
    log.info("aggregates_rebuilt", politician_id=politician_id, buckets=count)
    return count
