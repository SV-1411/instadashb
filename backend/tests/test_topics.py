"""WP9 topic tests: dictionary matching, LLM fallback, DB assignment."""

from __future__ import annotations

from app.clients.llm import FakeLlmClient
from app.core.timezone import now_ist
from app.models.mention import Mention
from app.models.politician import Politician
from app.services.topics import assign_topics_recent, dictionary_topics, llm_topics
from sqlalchemy.orm import Session


def test_dictionary_topics_matches_keywords() -> None:
    assert "roads" in dictionary_topics("the road is full of potholes")
    assert "corruption" in dictionary_topics("corruption everywhere in the office")
    assert "water" in dictionary_topics("no water supply for days")
    assert dictionary_topics("hello there friend") == []


def test_llm_topics_parses_fake_json() -> None:
    out = llm_topics("the road and the water problem", FakeLlmClient())
    assert "roads" in out and "water" in out


def test_assign_topics_recent_updates_mentions(db_session: Session) -> None:
    pol = Politician(name="Topic Demo")
    db_session.add(pol)
    db_session.commit()
    db_session.refresh(pol)

    db_session.add(
        Mention(
            politician_id=pol.id,
            platform="ig",
            source_type="comment",
            platform_mention_id="t1",
            raw_text="worst roads ever",
            language="en",
            sentiment_score=-0.8,
            sentiment_label="negative",
            topics=[],
            likes_count=0,
            platform_ts=now_ist(),
            processed=True,
        )
    )
    db_session.commit()

    updated = assign_topics_recent(db_session, pol.id, llm=FakeLlmClient())
    assert updated == 1
    m = db_session.query(Mention).filter_by(politician_id=pol.id).one()
    assert "roads" in m.topics
