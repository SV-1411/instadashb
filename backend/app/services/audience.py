"""Audience snapshot (WP4): write one city-level `audience_geo` row-set per day
from the Meta client. City-level only — Meta gives no finer geography."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clients.meta import MetaClient
from app.core.logging import get_logger
from app.core.timezone import now_ist
from app.models.audience_geo import AudienceGeo
from app.models.politician import Politician

log = get_logger("services.audience")


def snapshot_audience_geo(db: Session, client: MetaClient, pol: Politician) -> int:
    """Write today's audience snapshot if not already present. Returns rows written."""
    today = now_ist().date()
    exists = db.execute(
        select(AudienceGeo.id)
        .where(AudienceGeo.politician_id == pol.id, AudienceGeo.snapshot_date == today)
        .limit(1)
    ).first()
    if exists is not None:
        return 0

    account = pol.ig_account_id or pol.fb_page_id or f"demo_{pol.id}"
    written = 0
    for c in client.get_audience_geo(account, pol.meta_token):
        db.add(
            AudienceGeo(
                politician_id=pol.id,
                snapshot_date=today,
                city=c.city,
                follower_pct=c.follower_pct,
                age_band=c.age_band,
                gender=c.gender,
            )
        )
        written += 1
    db.commit()
    log.info("audience_snapshot", politician_id=pol.id, rows=written)
    return written
