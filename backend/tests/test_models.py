"""Model + DB tests: meta_token is ciphertext at rest; core tables round-trip."""

from __future__ import annotations

from datetime import date

from app.core.timezone import now_ist
from app.models import Aggregate, AudienceGeo, Mention, Politician, PostMetric
from sqlalchemy import text
from sqlalchemy.orm import Session


def test_meta_token_encrypted_at_rest(db_session: Session) -> None:
    p = Politician(
        name="Test Netaji", constituency="Pune", state="MH", meta_token="SUPER-SECRET-TOKEN"
    )
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)

    # Decrypted transparently on read…
    assert p.meta_token == "SUPER-SECRET-TOKEN"

    # …but ciphertext at rest (raw column must not contain the plaintext).
    raw = db_session.execute(
        text("SELECT meta_token FROM politicians WHERE id = :i"), {"i": p.id}
    ).scalar_one()
    assert raw != "SUPER-SECRET-TOKEN"
    assert "SECRET" not in raw


def test_core_tables_roundtrip(db_session: Session) -> None:
    p = Politician(name="Demo")
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)

    db_session.add_all(
        [
            Mention(
                politician_id=p.id,
                platform="fb",
                source_type="comment",
                raw_text="great work",
                sentiment_label="positive",
                topics=["roads", "water"],
            ),
            PostMetric(politician_id=p.id, platform="fb", post_id="post_1", likes=10),
            AudienceGeo(
                politician_id=p.id, snapshot_date=date(2026, 6, 9), city="Pune", follower_pct=12.5
            ),
            Aggregate(
                politician_id=p.id,
                bucket_hour=now_ist(),
                sentiment_score=72,
                positive_count=3,
                negative_count=1,
                neutral_count=2,
                top_topics=[{"topic": "roads", "count": 5}],
            ),
        ]
    )
    db_session.commit()

    m = db_session.query(Mention).filter_by(politician_id=p.id).one()
    assert m.topics == ["roads", "water"]
    assert db_session.query(Aggregate).filter_by(politician_id=p.id).one().sentiment_score == 72
