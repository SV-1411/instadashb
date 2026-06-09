"""WP11 ground-intelligence manual input test."""

from __future__ import annotations

from app.api.content import ground_input
from app.models.politician import Politician
from app.schemas.content import GroundInputIn
from sqlalchemy.orm import Session


def test_ground_input_stores_and_enriches(db_session: Session) -> None:
    pol = Politician(name="Ground Demo")
    db_session.add(pol)
    db_session.commit()
    db_session.refresh(pol)

    out = ground_input(
        GroundInputIn(politician_id=pol.id, text="angry crowd about water in Pune"),
        db_session,
    )
    assert out.stored is True
    assert out.inferred_city == "Pune"
    assert "water" in out.topics
