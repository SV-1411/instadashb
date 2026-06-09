"""Dashboard read API (architecture rule 1: reads ONLY Postgres/Redis).

Every endpoint serves pre-computed aggregates; none calls Meta/X. Results are
cached in Redis with a short TTL and fall back to Postgres on a cache miss.
"""

from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.cache import cache_get, cache_set
from app.core.timezone import now_ist
from app.database import get_db
from app.models.aggregate import Aggregate
from app.models.mention import Mention
from app.models.politician import Politician
from app.models.post_metric import PostMetric
from app.schemas.dashboard import (
    CityGeoOut,
    CommandCenterOut,
    CrisisOut,
    IdentityOut,
    PoliticianOut,
    TopPostOut,
    TrendPoint,
)

router = APIRouter(prefix="/api", tags=["dashboard"])


def _token_status(db: Session, pol: Politician) -> str:
    """Read token health from the worker-maintained cache; fall back to a local,
    network-free check (presence of an encrypted token)."""
    cached = cache_get(f"token_health:{pol.id}")
    if cached:
        return str(cached.get("status", "unknown"))
    return "connected" if pol.meta_token else "missing"


def _require(db: Session, politician_id: int) -> Politician:
    pol = db.get(Politician, politician_id)
    if pol is None:
        raise HTTPException(status_code=404, detail="politician not found")
    return pol


@router.get("/politicians", response_model=list[PoliticianOut])
def list_politicians(db: Session = Depends(get_db)) -> list[PoliticianOut]:
    pols = db.execute(select(Politician).order_by(Politician.name)).scalars().all()
    return [
        PoliticianOut(
            id=p.id,
            name=p.name,
            constituency=p.constituency,
            state=p.state,
            token_status=_token_status(db, p),
        )
        for p in pols
    ]


@router.get("/command-center/{politician_id}", response_model=CommandCenterOut)
def command_center(politician_id: int, db: Session = Depends(get_db)) -> CommandCenterOut:
    cache_key = f"cc:{politician_id}"
    cached = cache_get(cache_key)
    if cached:
        return CommandCenterOut.model_validate(cached)

    pol = _require(db, politician_id)
    rows = (
        db.execute(
            select(Aggregate)
            .where(Aggregate.politician_id == pol.id)
            .order_by(Aggregate.bucket_hour.desc())
            .limit(24)
        )
        .scalars()
        .all()
    )
    rows = list(reversed(rows))  # chronological for the trend

    trend = [
        TrendPoint(
            bucket_hour=a.bucket_hour,
            sentiment_score=a.sentiment_score,
            positive_count=a.positive_count,
            negative_count=a.negative_count,
            neutral_count=a.neutral_count,
            is_spike=a.is_spike,
        )
        for a in rows
    ]
    latest = rows[-1] if rows else None
    pos = sum(a.positive_count for a in rows)
    neg = sum(a.negative_count for a in rows)
    neu = sum(a.neutral_count for a in rows)
    total = pos + neg + neu
    # Headline gauge = average over the window (representative "overall" mood);
    # the spike banner separately flags the acute current hour.
    avg_score = round(sum(a.sentiment_score for a in rows) / len(rows)) if rows else 50

    # Calibrating until there is >24h of history to baseline against.
    oldest_metric = db.execute(
        select(func.min(PostMetric.captured_at)).where(PostMetric.politician_id == pol.id)
    ).scalar_one_or_none()
    calibrating = oldest_metric is None or oldest_metric > now_ist() - timedelta(days=1)

    out = CommandCenterOut(
        politician_id=pol.id,
        sentiment_score=avg_score,
        positive_count=pos,
        negative_count=neg,
        neutral_count=neu,
        total_mentions=total,
        active_spike=bool(latest.is_spike) if latest else False,
        trend=trend,
        calibrating=calibrating,
        generated_at=now_ist(),
    )
    cache_set(cache_key, out.model_dump())
    return out


@router.get("/identity/{politician_id}", response_model=IdentityOut)
def identity(politician_id: int, db: Session = Depends(get_db)) -> IdentityOut:
    pol = _require(db, politician_id)
    metrics = (
        db.execute(
            select(PostMetric)
            .where(PostMetric.politician_id == pol.id)
            .order_by(PostMetric.captured_at.desc())
            .limit(200)
        )
        .scalars()
        .all()
    )

    # Rank by engagement; keep the latest snapshot per post_id.
    best: dict[str, PostMetric] = {}
    for m in metrics:
        if m.post_id not in best:
            best[m.post_id] = m
    ranked = sorted(
        best.values(),
        key=lambda m: m.likes + m.comments_count + m.shares + m.saves,
        reverse=True,
    )[:10]

    top_posts = [
        TopPostOut(
            post_id=m.post_id,
            platform=m.platform,
            likes=m.likes,
            comments_count=m.comments_count,
            shares=m.shares,
            reach=m.reach,
            engagement=m.likes + m.comments_count + m.shares + m.saves,
        )
        for m in ranked
    ]

    # Latest audience snapshot (city-level only — Meta limitation).
    from app.models.audience_geo import AudienceGeo

    latest_date = db.execute(
        select(func.max(AudienceGeo.snapshot_date)).where(AudienceGeo.politician_id == pol.id)
    ).scalar_one_or_none()
    audience: list[CityGeoOut] = []
    if latest_date is not None:
        geo = (
            db.execute(
                select(AudienceGeo).where(
                    AudienceGeo.politician_id == pol.id,
                    AudienceGeo.snapshot_date == latest_date,
                )
            )
            .scalars()
            .all()
        )
        audience = [
            CityGeoOut(
                city=g.city or "?",
                follower_pct=g.follower_pct or 0.0,
                age_band=g.age_band,
                gender=g.gender,
            )
            for g in geo
        ]

    return IdentityOut(
        politician_id=pol.id, top_posts=top_posts, audience=audience, generated_at=now_ist()
    )


@router.get("/crisis/{politician_id}", response_model=CrisisOut)
def crisis(politician_id: int, db: Session = Depends(get_db)) -> CrisisOut:
    pol = _require(db, politician_id)
    spikes = (
        db.execute(
            select(Aggregate)
            .where(Aggregate.politician_id == pol.id, Aggregate.is_spike.is_(True))
            .order_by(Aggregate.bucket_hour.desc())
            .limit(20)
        )
        .scalars()
        .all()
    )
    dm_count = db.execute(
        select(func.count(Mention.id)).where(
            Mention.politician_id == pol.id, Mention.source_type == "dm_meta"
        )
    ).scalar_one()
    recent = [
        TrendPoint(
            bucket_hour=a.bucket_hour,
            sentiment_score=a.sentiment_score,
            positive_count=a.positive_count,
            negative_count=a.negative_count,
            neutral_count=a.neutral_count,
            is_spike=a.is_spike,
        )
        for a in spikes
    ]
    active = bool(spikes and spikes[0].bucket_hour >= now_ist() - timedelta(hours=2))
    return CrisisOut(
        politician_id=pol.id,
        active_spike=active,
        recent_spikes=recent,
        dm_count=dm_count,
        generated_at=now_ist(),
    )
