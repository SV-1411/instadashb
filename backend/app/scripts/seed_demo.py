"""Seed deterministic demo data so the dashboard is fully populated offline.

Creates one demo politician with ~8 days of hourly mentions + post_metrics
(mostly positive/neutral, a low negative baseline), a city audience snapshot,
and a burst of negative mentions in the CURRENT hour to trigger a real spike +
one FCM push. Idempotent: safe to re-run (dedupe on platform_mention_id).

Run:  python -m app.scripts.seed_demo
"""

from __future__ import annotations

import random
from datetime import timedelta

from sqlalchemy import select

from app.clients.fcm import FakeFcmClient
from app.clients.llm import FakeLlmClient
from app.clients.meta import FakeMetaClient
from app.core.logging import get_logger
from app.core.timezone import floor_to_hour_ist, now_ist
from app.database import SessionLocal
from app.models.audience_geo import AudienceGeo
from app.models.mention import Mention
from app.models.politician import Politician
from app.models.post_metric import PostMetric
from app.services.aggregate import upsert_aggregate
from app.services.ai_brief import generate_daily_brief
from app.services.geo_infer import CITY_COORDS, CITY_TO_AREA
from app.services.sentiment_reactions import classify_comment
from app.services.spike import detect_spike
from app.services.topics import dictionary_topics

log = get_logger("scripts.seed_demo")

POS = [
    "great work on Pune roads",
    "best water project in Mumbai",
    "well done on the new hospital",
    "proud of the jobs created",
    "thank you for the metro rally",
    "good schools now in Nashik",
    "great electricity supply improvement",
    "best leader, well done sir",
]
NEG = [
    "worst roads in Pune",
    "corruption in water supply Mumbai",
    "nothing done on power cuts Nagpur",
    "hospitals fail the people",
    "shame on the jobs situation",
    "worst crime and safety record",
    "corruption everywhere, nothing changed",
    "worst electricity load shedding",
]
NEU = [
    "when is the next rally in Nashik",
    "please visit our area soon",
    "info needed on the water scheme",
    "namaste, any update on schools",
]


def _get_or_create_politician(db) -> Politician:  # type: ignore[no-untyped-def]
    pol = db.execute(
        select(Politician).where(Politician.name == "Demo Netaji")
    ).scalar_one_or_none()
    if pol is None:
        pol = Politician(
            name="Demo Netaji",
            constituency="Pune Cantonment",
            state="Maharashtra",
            ig_account_id="demo_ig",
            fb_page_id="demo_fb",
            meta_token="demo-long-lived-token",
            x_handle="@demo_netaji",
        )
        db.add(pol)
        db.commit()
        db.refresh(pol)
    return pol


def seed() -> int:
    rng = random.Random(42)  # deterministic
    db = SessionLocal()
    try:
        pol = _get_or_create_politician(db)
        now = floor_to_hour_ist(now_ist())
        buckets: set = set()

        # Idempotency: clear prior seed rows so re-running regenerates a fresh
        # current-hour spike (and never collides with the mention unique constraint).
        db.query(Mention).filter(
            Mention.politician_id == pol.id, Mention.platform_mention_id.like("seed_%")
        ).delete(synchronize_session=False)
        db.query(PostMetric).filter(
            PostMetric.politician_id == pol.id, PostMetric.post_id.like("seed_%")
        ).delete(synchronize_session=False)
        db.commit()

        # ── 8 days of hourly-ish history (every 2 hours) ─────────────────────
        for h in range(8 * 24, 0, -2):
            bucket = now - timedelta(hours=h)
            buckets.add(bucket)
            post_id = f"seed_post_{pol.id}_{int(h)}"
            db.add(
                PostMetric(
                    politician_id=pol.id,
                    platform="ig" if h % 4 == 0 else "fb",
                    post_id=post_id,
                    reach=rng.randint(2000, 40000),
                    impressions=rng.randint(3000, 60000),
                    likes=rng.randint(100, 4000),
                    comments_count=rng.randint(5, 15),
                    shares=rng.randint(0, 600),
                    saves=rng.randint(0, 300),
                    react_like=rng.randint(100, 2500),
                    react_love=rng.randint(20, 1200),
                    react_haha=rng.randint(0, 200),
                    react_wow=rng.randint(0, 150),
                    react_sad=rng.randint(0, 200),
                    react_angry=rng.randint(0, 250),
                    captured_at=bucket,
                )
            )
            n = rng.randint(5, 10)
            for j in range(n):
                roll = rng.random()
                text = (
                    NEG[rng.randrange(len(NEG))]
                    if roll < 0.10
                    else (
                        NEU[rng.randrange(len(NEU))]
                        if roll < 0.45
                        else POS[rng.randrange(len(POS))]
                    )
                )
                score, label = classify_comment(text)
                db.add(
                    Mention(
                        politician_id=pol.id,
                        platform="ig",
                        source_type="comment",
                        platform_mention_id=f"seed_{pol.id}_{int(h)}_{j}",
                        raw_text=text,
                        language="en",
                        sentiment_score=score,
                        sentiment_label=label,
                        topics=[],
                        likes_count=rng.randint(0, 40),
                        platform_ts=bucket + timedelta(minutes=j * 3),
                        processed=True,
                    )
                )
        db.commit()

        # ── Current-hour NEGATIVE BURST -> triggers a spike ──────────────────
        buckets.add(now)
        db.add(
            PostMetric(
                politician_id=pol.id,
                platform="fb",
                post_id=f"seed_post_{pol.id}_now",
                reach=60000,
                impressions=90000,
                likes=800,
                comments_count=25,
                shares=50,
                saves=10,
                react_like=400,
                react_love=50,
                react_haha=10,
                react_wow=5,
                react_sad=300,
                react_angry=900,
                captured_at=now,
            )
        )
        for j in range(25):
            text = NEG[j % len(NEG)]
            score, label = classify_comment(text)
            db.add(
                Mention(
                    politician_id=pol.id,
                    platform="fb",
                    source_type="comment",
                    platform_mention_id=f"seed_{pol.id}_now_{j}",
                    raw_text=text,
                    language="en",
                    sentiment_score=score,
                    sentiment_label=label,
                    topics=[],
                    likes_count=2,
                    platform_ts=now + timedelta(minutes=j % 50),
                    processed=True,
                )
            )
        # A few claim/rumor mentions so the misinformation flag has something to show.
        for j in range(6):
            text = "viral video is fake news, total rumor" if j % 2 == 0 else "fake photo spreading"
            db.add(
                Mention(
                    politician_id=pol.id,
                    platform="x",
                    source_type="mention",
                    platform_mention_id=f"seed_{pol.id}_claim_{j}",
                    raw_text=text,
                    language="en",
                    sentiment_score=-0.5,
                    sentiment_label="negative",
                    topics=[],
                    likes_count=1,
                    platform_ts=now + timedelta(minutes=j),
                    processed=True,
                )
            )
        db.commit()

        # ── Audience snapshot (city-level) ───────────────────────────────────
        meta = FakeMetaClient()
        today = now.date()
        existing = db.execute(
            select(AudienceGeo).where(
                AudienceGeo.politician_id == pol.id, AudienceGeo.snapshot_date == today
            )
        ).first()
        if existing is None:
            for ac in meta.get_audience_geo(pol.ig_account_id or "demo", pol.meta_token):
                db.add(
                    AudienceGeo(
                        politician_id=pol.id,
                        snapshot_date=today,
                        city=ac.city,
                        follower_pct=ac.follower_pct,
                        age_band=ac.age_band,
                        gender=ac.gender,
                    )
                )
            db.commit()

        # ── Assign topics + spread mentions across cities (for the India map) ─
        cities = list(CITY_COORDS.keys())[:8]
        for idx, m in enumerate(
            db.execute(select(Mention).where(Mention.politician_id == pol.id)).scalars()
        ):
            if not m.topics:
                topics = dictionary_topics(m.raw_text or "")
                if topics:
                    m.topics = topics
            if m.inferred_city is None and m.source_type != "dm_meta":
                city = cities[idx % len(cities)]
                m.inferred_city = city
                m.inferred_area = CITY_TO_AREA.get(city)
        db.commit()

        # ── Build aggregates for every seeded bucket + run spike detection ───
        for b in sorted(buckets):
            upsert_aggregate(db, pol.id, b)
        fcm = FakeFcmClient()
        result = detect_spike(db, fcm, pol.id, now)

        # ── Generate today's AI brief (Fake LLM — seeding is always demo) ────
        generate_daily_brief(db, FakeLlmClient(), pol.id, force=True)

        log.info(
            "seed_done",
            politician_id=pol.id,
            buckets=len(buckets),
            spiked=result.spiked,
            current_negative=result.current_negative,
            threshold=round(result.threshold, 2),
        )
        print(
            f"Seeded politician id={pol.id} 'Demo Netaji' | buckets={len(buckets)} | "
            f"current-hour spike={result.spiked} (neg={result.current_negative}, "
            f"threshold={result.threshold:.1f}, push_fired={result.push_fired})"
        )
        return pol.id
    finally:
        db.close()


if __name__ == "__main__":
    seed()
