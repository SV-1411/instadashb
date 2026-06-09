"""WP9/WP11 read-API tests: public voice, trends, ai-brief (DB/Redis only)."""

from __future__ import annotations

from app.api.content import ai_brief, public_voice, trends
from app.core.timezone import floor_to_hour_ist, now_ist
from app.models.aggregate import Aggregate
from app.models.mention import Mention
from app.models.politician import Politician
from sqlalchemy.orm import Session


def _seed(db: Session) -> Politician:
    pol = Politician(name="Content Demo")
    db.add(pol)
    db.commit()
    db.refresh(pol)

    now = floor_to_hour_ist(now_ist())
    db.add_all(
        [
            Mention(
                politician_id=pol.id,
                platform="ig",
                source_type="comment",
                platform_mention_id="c1",
                raw_text="worst roads",
                language="en",
                sentiment_score=-0.8,
                sentiment_label="negative",
                topics=["roads"],
                likes_count=1,
                platform_ts=now,
                processed=True,
            ),
            Mention(
                politician_id=pol.id,
                platform="x",
                source_type="mention",
                platform_mention_id="x1",
                raw_text="great work",
                language="en",
                sentiment_score=0.8,
                sentiment_label="positive",
                topics=[],
                likes_count=5,
                platform_ts=now,
                processed=True,
            ),
        ]
    )
    db.add(
        Aggregate(
            politician_id=pol.id,
            bucket_hour=now,
            sentiment_score=50,
            positive_count=1,
            negative_count=1,
            neutral_count=0,
            top_topics=[{"topic": "roads", "count": 1}],
            is_spike=False,
        )
    )
    db.commit()
    return pol


def test_public_voice_groups_and_samples(db_session: Session) -> None:
    pol = _seed(db_session)
    pv = public_voice(pol.id, db_session)
    assert pv.by_sentiment["negative"] == 1
    assert pv.by_sentiment["positive"] == 1
    assert pv.by_platform["x"] == 1
    assert any("roads" in s.topics for s in pv.samples)


def test_trends_aggregates_topics(db_session: Session) -> None:
    pol = _seed(db_session)
    tr = trends(pol.id, db_session)
    assert any(t.topic == "roads" for t in tr.top_topics)
    assert len(tr.series) >= 1


def test_ai_brief_reads_cache_only(db_session: Session) -> None:
    pol = _seed(db_session)
    # No brief generated for this fresh politician/day -> placeholder, not an LLM call.
    ab = ai_brief(pol.id, db_session)
    assert ab.available is False
    assert ab.summary
