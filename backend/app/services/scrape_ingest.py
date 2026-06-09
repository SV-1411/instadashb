"""Ingest scraped public mentions into the unified `mentions` table
(source_type="mention"). Idempotent via platform_mention_id, like Meta ingestion."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clients.scraper import ScraperClient
from app.core.logging import get_logger
from app.models.mention import Mention
from app.services.sentiment_reactions import classify_comment

log = get_logger("services.scrape_ingest")


def ingest_scraped(
    db: Session, client: ScraperClient, politician_id: int, queries: list[str]
) -> int:
    """Pull scraped mentions for the given queries; write new ones. Returns count."""
    if not queries:
        return 0
    scraped = client.search(queries)
    existing = {
        r[0]
        for r in db.execute(
            select(Mention.platform_mention_id).where(
                Mention.politician_id == politician_id,
                Mention.source_type == "mention",
                Mention.platform_mention_id.is_not(None),
            )
        ).all()
    }
    written = 0
    for s in scraped:
        if s.platform_id in existing:
            continue
        existing.add(s.platform_id)
        score, label = classify_comment(s.text)
        db.add(
            Mention(
                politician_id=politician_id,
                platform="ig",
                source_type="mention",
                platform_mention_id=s.platform_id,
                raw_text=s.text,
                language="und",
                sentiment_score=score,
                sentiment_label=label,
                topics=[],
                likes_count=s.likes,
                platform_ts=s.created_at,
                processed=False,  # NLP batch refines scraped mentions too
            )
        )
        written += 1
    db.commit()
    log.info("scrape_ingest_done", politician_id=politician_id, written=written)
    return written
