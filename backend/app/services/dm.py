"""ManyChat DM handling (WP6). We store DM *metadata only* (subscriber, keyword,
timestamp) as a `dm_meta` mention — never DM content (Meta policy)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.timezone import now_ist
from app.models.mention import Mention

log = get_logger("services.dm")


def handle_dm_event(
    db: Session,
    politician_id: int,
    event_id: str,
    keyword: str | None,
    platform: str = "ig",
) -> bool:
    """Store one DM event as metadata. Idempotent on event_id. Returns True if written."""
    existing = db.execute(
        select(Mention.id).where(
            Mention.politician_id == politician_id,
            Mention.source_type == "dm_meta",
            Mention.platform_mention_id == event_id,
        )
    ).first()
    if existing is not None:
        return False

    db.add(
        Mention(
            politician_id=politician_id,
            platform=platform,
            source_type="dm_meta",
            platform_mention_id=event_id,
            raw_text=None,  # never store DM content
            language=None,
            sentiment_score=None,
            sentiment_label=None,
            topics=[keyword] if keyword else [],
            likes_count=0,
            platform_ts=now_ist(),
            processed=True,
        )
    )
    db.commit()
    log.info("dm_event_stored", politician_id=politician_id, keyword=keyword)
    return True
