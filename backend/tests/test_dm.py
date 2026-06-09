"""WP6 ManyChat DM tests: metadata-only storage + dedupe + webhook endpoint."""

from __future__ import annotations

from app.api.webhooks_manychat import ManyChatEvent, manychat_webhook
from app.models.mention import Mention
from app.models.politician import Politician
from app.services.dm import handle_dm_event
from sqlalchemy import func, select
from sqlalchemy.orm import Session


def _pol(db: Session) -> Politician:
    p = Politician(name="DM Demo")
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def test_handle_dm_event_stores_metadata_only(db_session: Session) -> None:
    pol = _pol(db_session)
    assert handle_dm_event(db_session, pol.id, "evt1", "support") is True
    assert handle_dm_event(db_session, pol.id, "evt1", "support") is False  # dedupe

    m = db_session.query(Mention).filter_by(politician_id=pol.id, source_type="dm_meta").one()
    assert m.raw_text is None  # never store DM content
    assert m.topics == ["support"]
    count = db_session.execute(
        select(func.count(Mention.id)).where(
            Mention.politician_id == pol.id, Mention.source_type == "dm_meta"
        )
    ).scalar_one()
    assert count == 1


def test_webhook_stores_for_first_politician(db_session: Session) -> None:
    pol = _pol(db_session)
    event = ManyChatEvent(event_id="evt-web-1", keyword="jobs", politician_id=pol.id)
    out = manychat_webhook(event, db=db_session, x_civicpulse_secret=None)
    assert out["stored"] is True
    assert out["politician_id"] == pol.id
