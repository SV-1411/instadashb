"""Aggregation tests: 0-100 score in range, counts correct, idempotent upsert."""

from __future__ import annotations

from datetime import timedelta

from app.core.timezone import floor_to_hour_ist, now_ist
from app.models.aggregate import Aggregate
from app.models.mention import Mention
from app.models.politician import Politician
from app.services.aggregate import upsert_aggregate
from sqlalchemy import func, select
from sqlalchemy.orm import Session


def _seed_bucket(db: Session, pol_id: int, bucket, pos: int, neg: int, neu: int) -> None:  # type: ignore[no-untyped-def]
    rows = []
    for i in range(pos):
        rows.append(("positive", 0.8, f"p{i}"))
    for i in range(neg):
        rows.append(("negative", -0.8, f"n{i}"))
    for i in range(neu):
        rows.append(("neutral", 0.0, f"x{i}"))
    for label, score, tag in rows:
        db.add(
            Mention(
                politician_id=pol_id,
                platform="ig",
                source_type="comment",
                platform_mention_id=f"{tag}_{label}",
                raw_text=label,
                language="en",
                sentiment_score=score,
                sentiment_label=label,
                topics=[],
                likes_count=0,
                platform_ts=bucket + timedelta(minutes=1),
                processed=True,
            )
        )
    db.commit()


def test_aggregate_counts_and_score_range(db_session: Session) -> None:
    pol = Politician(name="Agg Demo")
    db_session.add(pol)
    db_session.commit()
    db_session.refresh(pol)

    bucket = floor_to_hour_ist(now_ist())
    _seed_bucket(db_session, pol.id, bucket, pos=6, neg=1, neu=3)

    agg = upsert_aggregate(db_session, pol.id, bucket)
    assert agg.positive_count == 6
    assert agg.negative_count == 1
    assert agg.neutral_count == 3
    assert 0 <= agg.sentiment_score <= 100
    # Mostly positive -> score should land above the neutral midpoint.
    assert agg.sentiment_score > 50


def test_aggregate_is_idempotent(db_session: Session) -> None:
    pol = Politician(name="Agg Idem")
    db_session.add(pol)
    db_session.commit()
    db_session.refresh(pol)

    bucket = floor_to_hour_ist(now_ist())
    _seed_bucket(db_session, pol.id, bucket, pos=4, neg=2, neu=2)

    first = upsert_aggregate(db_session, pol.id, bucket)
    score1, id1 = first.sentiment_score, first.id
    second = upsert_aggregate(db_session, pol.id, bucket)

    assert second.id == id1  # same row, no duplicate
    assert second.sentiment_score == score1  # deterministic
    n_rows = db_session.execute(
        select(func.count(Aggregate.id)).where(
            Aggregate.politician_id == pol.id, Aggregate.bucket_hour == bucket
        )
    ).scalar_one()
    assert n_rows == 1
