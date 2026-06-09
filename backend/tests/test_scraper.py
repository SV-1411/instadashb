"""Scraper supplement tests: fake client yields mentions; ingest dedupes."""

from __future__ import annotations

from app.clients.scraper import FakeScraperClient
from app.models.mention import Mention
from app.models.politician import Politician
from app.services.scrape_ingest import ingest_scraped
from sqlalchemy import func, select
from sqlalchemy.orm import Session


def test_fake_scraper_returns_mentions() -> None:
    out = FakeScraperClient().search(["@demo", "#demo"])
    assert len(out) == 10  # 5 templates x 2 queries
    assert all(m.platform_id.startswith("scrape_") for m in out)


def test_scrape_ingest_writes_and_dedupes(db_session: Session) -> None:
    pol = Politician(name="Scrape Demo")
    db_session.add(pol)
    db_session.commit()
    db_session.refresh(pol)

    client = FakeScraperClient()
    first = ingest_scraped(db_session, client, pol.id, ["@demo"])
    second = ingest_scraped(db_session, client, pol.id, ["@demo"])

    assert first == 5
    assert second == 0  # all deduped on re-run
    total = db_session.execute(
        select(func.count(Mention.id)).where(
            Mention.politician_id == pol.id, Mention.source_type == "mention"
        )
    ).scalar_one()
    assert total == 5


def test_scrape_ingest_empty_queries_noop(db_session: Session) -> None:
    pol = Politician(name="Empty Q")
    db_session.add(pol)
    db_session.commit()
    db_session.refresh(pol)
    assert ingest_scraped(db_session, FakeScraperClient(), pol.id, []) == 0
