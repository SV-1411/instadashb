"""WP10 tests: geo inference + misinformation claim-volume flag, and the
geo/misinfo/growth read endpoints."""

from __future__ import annotations

from app.api.content import geo, growth, misinfo
from app.core.timezone import floor_to_hour_ist, now_ist
from app.models.mention import Mention
from app.models.politician import Politician
from app.models.post_metric import PostMetric
from app.services.geo_infer import assign_geo_recent, infer_location
from app.services.misinfo import detect_misinformation
from sqlalchemy.orm import Session


def _pol(db: Session) -> Politician:
    p = Politician(name="Geo Demo")
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _mention(pol_id: int, tag: str, text: str, when, city: str | None = None) -> Mention:
    return Mention(
        politician_id=pol_id,
        platform="ig",
        source_type="comment",
        platform_mention_id=tag,
        raw_text=text,
        language="en",
        sentiment_score=-0.6,
        sentiment_label="negative",
        topics=[],
        likes_count=0,
        inferred_city=city,
        platform_ts=when,
        processed=True,
    )


def test_infer_location_matches_known_city() -> None:
    assert infer_location("the roads in Pune are terrible")[0] == "Pune"
    assert infer_location("no city here") == (None, None)


def test_assign_geo_recent_updates(db_session: Session) -> None:
    pol = _pol(db_session)
    db_session.add(_mention(pol.id, "g1", "Mumbai water crisis", now_ist()))
    db_session.commit()
    assert assign_geo_recent(db_session, pol.id) == 1
    assert db_session.query(Mention).filter_by(politician_id=pol.id).one().inferred_city == "Mumbai"


def test_misinfo_flags_on_claim_volume(db_session: Session) -> None:
    pol = _pol(db_session)
    now = now_ist()
    for i in range(6):
        db_session.add(_mention(pol.id, f"c{i}", "this viral video is fake news", now))
    db_session.commit()
    flag = detect_misinformation(db_session, pol.id)
    assert flag.flagged is True
    assert flag.claim_volume >= 6


def test_geo_and_growth_endpoints(db_session: Session) -> None:
    pol = _pol(db_session)
    now = floor_to_hour_ist(now_ist())
    db_session.add(_mention(pol.id, "p1", "Pune roads", now, city="Pune"))
    db_session.add(
        PostMetric(
            politician_id=pol.id,
            platform="ig",
            post_id="pm1",
            reach=1000,
            likes=50,
            comments_count=5,
            shares=2,
            saves=1,
            captured_at=now,
        )
    )
    db_session.commit()

    g = geo(pol.id, db_session)
    assert any(c.city == "Pune" for c in g.cities)

    gr = growth(pol.id, db_session)
    assert gr.series and gr.series[-1].reach == 1000

    mf = misinfo(pol.id, db_session)
    assert mf.flagged is False  # only one non-claim mention
