"""Ingest X (Twitter) mentions into the unified `mentions` table (platform="x").
Idempotent via platform_mention_id, like the other ingestion paths."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clients.socialdata import SocialDataClient
from app.core.logging import get_logger
from app.models.mention import Mention
from app.services.sentiment_reactions import classify_comment

log = get_logger("services.x_ingest")


def ingest_x(db: Session, client: SocialDataClient, politician_id: int, queries: list[str]) -> int:
    """Pull X mentions for the given queries; write new ones. Returns count written."""
    if not queries:
        return 0
    existing = {
        r[0]
        for r in db.execute(
            select(Mention.platform_mention_id).where(
                Mention.politician_id == politician_id,
                Mention.platform == "x",
                Mention.platform_mention_id.is_not(None),
            )
        ).all()
    }
    written = 0
    for query in queries:
        for x in client.search(query):
            if x.platform_id in existing:
                continue
            existing.add(x.platform_id)
            score, label = classify_comment(x.text)  # provisional; NLP batch refines
            db.add(
                Mention(
                    politician_id=politician_id,
                    platform="x",
                    source_type="mention",
                    platform_mention_id=x.platform_id,
                    raw_text=x.text,
                    language="und",
                    sentiment_score=score,
                    sentiment_label=label,
                    topics=[],
                    likes_count=x.likes,
                    platform_ts=x.created_at,
                    processed=False,
                )
            )
            written += 1
    db.commit()
    log.info("x_ingest_done", politician_id=politician_id, written=written)
    return written
