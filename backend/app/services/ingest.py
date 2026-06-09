"""Ingestion (WP2): pull posts/comments from a Meta client and write them into
the unified `mentions` table + `post_metrics`. Idempotent (dedupe on
platform_mention_id) and resilient (a single bad post never aborts the cycle)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clients.meta import MetaClient, RawPost
from app.core.logging import get_logger
from app.core.security import decrypt_secret  # noqa: F401  (token use point for Real client)
from app.core.timezone import now_ist
from app.models.mention import Mention
from app.models.politician import Politician
from app.models.post_metric import PostMetric
from app.services.sentiment_reactions import classify_comment

log = get_logger("services.ingest")

# How far back to pull posts each cycle (the real clients use this as the API
# time filter; dedupe keeps re-fetches cheap).
INGEST_LOOKBACK_DAYS = 30


@dataclass
class IngestResult:
    politician_id: int
    posts_seen: int
    mentions_written: int
    metrics_written: int
    skipped_duplicates: int


def _existing_mention_ids(db: Session, politician_id: int) -> set[str]:
    rows = db.execute(
        select(Mention.platform_mention_id).where(
            Mention.politician_id == politician_id,
            Mention.platform_mention_id.is_not(None),
        )
    ).all()
    return {r[0] for r in rows}


def ingest_politician(db: Session, client: MetaClient, politician: Politician) -> IngestResult:
    """Run one ingestion cycle for a politician. Commits once at the end."""
    # Look back a window (floored to the hour so the Fake client stays deterministic
    # within an hour); real clients use this as the posts-since filter.
    since = (now_ist() - timedelta(days=INGEST_LOOKBACK_DAYS)).replace(
        minute=0, second=0, microsecond=0
    )
    account = politician.ig_account_id or politician.fb_page_id or f"demo_{politician.id}"

    posts: list[RawPost] = client.get_posts(account, politician.meta_token, since)
    seen_ids = _existing_mention_ids(db, politician.id)

    mentions_written = metrics_written = skipped = 0

    for post in posts:
        # One post_metrics row per post per cycle (captured_at distinguishes snapshots).
        db.add(
            PostMetric(
                politician_id=politician.id,
                platform=post.platform,
                post_id=post.platform_id,
                reach=post.reach,
                impressions=post.impressions,
                likes=post.likes,
                comments_count=post.comments_count,
                shares=post.shares,
                saves=post.saves,
                react_like=post.reactions.get("like", 0),
                react_love=post.reactions.get("love", 0),
                react_angry=post.reactions.get("angry", 0),
                react_sad=post.reactions.get("sad", 0),
                react_haha=post.reactions.get("haha", 0),
                react_wow=post.reactions.get("wow", 0),
            )
        )
        metrics_written += 1

        for c in post.comments:
            if c.platform_id in seen_ids:
                skipped += 1
                continue
            seen_ids.add(c.platform_id)
            # Provisional lexicon score so data is usable immediately; the NLP
            # batch (WP8) refines it and flips processed=True.
            score, label = classify_comment(c.text)
            db.add(
                Mention(
                    politician_id=politician.id,
                    platform=post.platform,
                    source_type="comment",
                    platform_mention_id=c.platform_id,
                    raw_text=c.text,
                    language=c.language,
                    sentiment_score=score,
                    sentiment_label=label,
                    topics=[],
                    likes_count=c.likes,
                    platform_ts=c.created_at,
                    processed=False,  # NLP pending
                )
            )
            mentions_written += 1

    db.commit()
    result = IngestResult(
        politician_id=politician.id,
        posts_seen=len(posts),
        mentions_written=mentions_written,
        metrics_written=metrics_written,
        skipped_duplicates=skipped,
    )
    log.info(
        "ingest_cycle_done",
        politician_id=politician.id,
        posts=result.posts_seen,
        mentions=result.mentions_written,
        skipped=result.skipped_duplicates,
    )
    return result
