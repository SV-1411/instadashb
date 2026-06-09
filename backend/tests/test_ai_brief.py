"""WP11 AI Brief tests: builds from aggregates via the (Fake) LLM, with fallback."""

from __future__ import annotations

from datetime import timedelta

from app.clients.llm import FakeLlmClient
from app.core.timezone import floor_to_hour_ist, now_ist
from app.models.aggregate import Aggregate
from app.models.politician import Politician
from app.services.ai_brief import generate_daily_brief
from sqlalchemy.orm import Session


def test_brief_generates_from_aggregates(db_session: Session) -> None:
    pol = Politician(name="Brief Demo")
    db_session.add(pol)
    db_session.commit()
    db_session.refresh(pol)

    now = floor_to_hour_ist(now_ist())
    for h in range(3):
        db_session.add(
            Aggregate(
                politician_id=pol.id,
                bucket_hour=now - timedelta(hours=h),
                sentiment_score=40,
                positive_count=2,
                negative_count=6,
                neutral_count=1,
                top_topics=[{"topic": "roads", "count": 4}],
                is_spike=(h == 0),
            )
        )
    db_session.commit()

    brief = generate_daily_brief(db_session, FakeLlmClient(), pol.id, force=True)
    assert brief.summary
    assert len(brief.actions) >= 1


def test_brief_handles_no_data(db_session: Session) -> None:
    pol = Politician(name="Empty Brief")
    db_session.add(pol)
    db_session.commit()
    db_session.refresh(pol)

    brief = generate_daily_brief(db_session, FakeLlmClient(), pol.id, force=True)
    assert "not enough data" in brief.summary.lower()
