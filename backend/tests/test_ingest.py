"""Ingestion tests: writes mentions+metrics from a Fake client; dedupes on re-run."""

from __future__ import annotations

from app.clients.meta import FakeMetaClient
from app.models.mention import Mention
from app.models.politician import Politician
from app.models.post_metric import PostMetric
from app.services.ingest import ingest_politician
from sqlalchemy import func, select
from sqlalchemy.orm import Session


def _demo_politician(db: Session) -> Politician:
    pol = Politician(name="Ingest Demo", ig_account_id="acct_1", meta_token="tok")
    db.add(pol)
    db.commit()
    db.refresh(pol)
    return pol


def test_ingest_writes_mentions_and_metrics(db_session: Session) -> None:
    pol = _demo_politician(db_session)
    client = FakeMetaClient(posts_per_cycle=4)

    result = ingest_politician(db_session, client, pol)

    assert result.posts_seen == 4
    assert result.mentions_written > 0
    n_mentions = db_session.execute(
        select(func.count(Mention.id)).where(Mention.politician_id == pol.id)
    ).scalar_one()
    n_metrics = db_session.execute(
        select(func.count(PostMetric.id)).where(PostMetric.politician_id == pol.id)
    ).scalar_one()
    assert n_mentions == result.mentions_written
    assert n_metrics == 4


def test_ingest_is_idempotent_on_rerun(db_session: Session) -> None:
    pol = _demo_politician(db_session)
    client = FakeMetaClient(posts_per_cycle=4)

    first = ingest_politician(db_session, client, pol)
    second = ingest_politician(db_session, client, pol)

    # Same deterministic data -> second cycle writes no new mentions (all deduped).
    assert second.mentions_written == 0
    assert second.skipped_duplicates == first.mentions_written
    total = db_session.execute(
        select(func.count(Mention.id)).where(Mention.politician_id == pol.id)
    ).scalar_one()
    assert total == first.mentions_written
