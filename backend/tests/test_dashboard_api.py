"""Dashboard read-API tests. These call the endpoint functions with a test
session and assert response shapes. They must work off DB data only (no external
calls), proving architecture rule 1 holds on read paths."""

from __future__ import annotations

from datetime import timedelta

import pytest
from app.api.dashboard import command_center, crisis, identity, list_politicians
from app.cache import cache_set
from app.core.timezone import floor_to_hour_ist, now_ist
from app.models.aggregate import Aggregate
from app.models.audience_geo import AudienceGeo
from app.models.politician import Politician
from app.models.post_metric import PostMetric
from fastapi import HTTPException
from sqlalchemy.orm import Session


def _seed(db: Session) -> Politician:
    pol = Politician(name="API Demo", constituency="Pune", state="MH", meta_token="tok")
    db.add(pol)
    db.commit()
    db.refresh(pol)

    now = floor_to_hour_ist(now_ist())
    for h in range(3):
        db.add(
            Aggregate(
                politician_id=pol.id,
                bucket_hour=now - timedelta(hours=h),
                sentiment_score=70 - h,
                positive_count=5,
                negative_count=1,
                neutral_count=2,
                top_topics=[],
                is_spike=(h == 0),
            )
        )
    db.add(
        PostMetric(
            politician_id=pol.id,
            platform="ig",
            post_id="p1",
            likes=100,
            comments_count=10,
            shares=5,
            saves=2,
            reach=2000,
            captured_at=now,
        )
    )
    db.add(
        AudienceGeo(
            politician_id=pol.id,
            snapshot_date=now.date(),
            city="Pune",
            follower_pct=22.0,
            age_band="25-34",
            gender="mixed",
        )
    )
    db.commit()
    # Ensure no stale Redis cache from a previous run interferes.
    cache_set(f"cc:{pol.id}", None, ttl=1)
    return pol


def test_list_and_command_center(db_session: Session) -> None:
    pol = _seed(db_session)

    pols = list_politicians(db_session)
    assert any(p.id == pol.id and p.name == "API Demo" for p in pols)

    cc = command_center(pol.id, db_session)
    assert cc.politician_id == pol.id
    assert 0 <= cc.sentiment_score <= 100
    assert cc.total_mentions == 3 * (5 + 1 + 2)
    assert cc.active_spike is True
    assert len(cc.trend) == 3


def test_identity_and_crisis(db_session: Session) -> None:
    pol = _seed(db_session)

    idn = identity(pol.id, db_session)
    assert idn.politician_id == pol.id
    assert len(idn.top_posts) == 1
    assert idn.top_posts[0].engagement == 100 + 10 + 5 + 2
    assert any(c.city == "Pune" for c in idn.audience)

    cr = crisis(pol.id, db_session)
    assert cr.politician_id == pol.id
    assert len(cr.recent_spikes) == 1


def test_missing_politician_404(db_session: Session) -> None:
    with pytest.raises(HTTPException) as exc:
        command_center(999999, db_session)
    assert exc.value.status_code == 404
