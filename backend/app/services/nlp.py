"""NLP pipeline (WP8): refine comment sentiment using Google NL, with cost
sampling and a lexicon fallback. The refined score lands in `mentions.sentiment_score`,
which the aggregator already uses as the 40% comment-NLP component of the 0-100 score.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clients.google_nl import GoogleNlClient
from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.models.mention import Mention
from app.services.sentiment_reactions import classify_comment, label_from_score

log = get_logger("services.nlp")


@dataclass
class NlpResult:
    score: float
    label: str
    language: str | None
    source: str  # "google_nl" | "lexicon"


def sample_in(key: str, rate: float) -> bool:
    """Deterministic cost gate: is this item in the NLP sample? Stable across re-runs."""
    if rate >= 1.0:
        return True
    if rate <= 0.0:
        return False
    h = int(hashlib.sha256(key.encode()).hexdigest(), 16)
    return (h % 100) < rate * 100


def score_text(text: str, sample_key: str, client: GoogleNlClient, settings: Settings) -> NlpResult:
    """Score one comment: call Google NL if sampled-in and available, else lexicon."""
    if text and sample_in(sample_key, settings.nlp_sample_rate):
        nl = client.analyze_sentiment(text)
        if nl is not None:
            return NlpResult(nl.score, label_from_score(nl.score), nl.language, "google_nl")
    score, label = classify_comment(text or "")
    return NlpResult(score, label, None, "lexicon")


def process_nlp_batch(
    db: Session,
    client: GoogleNlClient,
    politician_id: int | None = None,
    limit: int = 500,
    settings: Settings | None = None,
) -> int:
    """Refine sentiment for unprocessed text mentions; mark them processed. Returns count."""
    settings = settings or get_settings()
    stmt = (
        select(Mention)
        .where(
            Mention.processed.is_(False),
            Mention.source_type.in_(("comment", "mention")),
            Mention.raw_text.is_not(None),
        )
        .limit(limit)
    )
    if politician_id is not None:
        stmt = stmt.where(Mention.politician_id == politician_id)

    mentions = db.execute(stmt).scalars().all()
    for m in mentions:
        key = m.platform_mention_id or str(m.id)
        result = score_text(m.raw_text or "", key, client, settings)
        m.sentiment_score = result.score
        m.sentiment_label = result.label
        if result.language:
            m.language = result.language
        m.processed = True
    db.commit()
    log.info("nlp_batch_done", politician_id=politician_id, processed=len(mentions))
    return len(mentions)
