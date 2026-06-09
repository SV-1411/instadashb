"""AI Brief (WP11): a daily LLM summary + recommended actions, built from the
pre-computed aggregates (NOT from raw external calls). Cached one-per-day in Redis."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cache import cache_get, cache_set
from app.clients.llm import LlmClient
from app.core.logging import get_logger
from app.core.timezone import floor_to_hour_ist, now_ist
from app.models.aggregate import Aggregate

log = get_logger("services.ai_brief")


@dataclass
class Brief:
    politician_id: int
    summary: str
    actions: list[str] = field(default_factory=list)
    generated_at: str = ""
    cached: bool = False


def _build_context(db: Session, politician_id: int) -> dict:
    """Summarize the last 24h of aggregates into a compact dict for the prompt."""
    since = floor_to_hour_ist(now_ist()) - timedelta(hours=24)
    rows = (
        db.execute(
            select(Aggregate)
            .where(Aggregate.politician_id == politician_id, Aggregate.bucket_hour >= since)
            .order_by(Aggregate.bucket_hour)
        )
        .scalars()
        .all()
    )
    if not rows:
        return {}
    latest = rows[-1]
    topic_counts: dict[str, int] = {}
    for r in rows:
        for item in r.top_topics or []:
            topic_counts[item["topic"]] = topic_counts.get(item["topic"], 0) + item.get("count", 0)
    top = sorted(topic_counts.items(), key=lambda kv: kv[1], reverse=True)[:5]
    return {
        "latest_score": latest.sentiment_score,
        "active_spike": latest.is_spike,
        "positive_24h": sum(r.positive_count for r in rows),
        "negative_24h": sum(r.negative_count for r in rows),
        "neutral_24h": sum(r.neutral_count for r in rows),
        "top_topics": [t for t, _ in top],
        "spike_hours": sum(1 for r in rows if r.is_spike),
    }


def generate_daily_brief(
    db: Session, llm: LlmClient, politician_id: int, force: bool = False
) -> Brief:
    """Return today's brief (cached) or generate it from aggregates via the LLM."""
    today = now_ist().date().isoformat()
    cache_key = f"brief:{politician_id}:{today}"
    if not force:
        cached = cache_get(cache_key)
        if cached:
            return Brief(**{**cached, "cached": True})

    ctx = _build_context(db, politician_id)
    if not ctx:
        return Brief(
            politician_id=politician_id,
            summary="Not enough data yet to generate a brief.",
            actions=[],
            generated_at=now_ist().isoformat(),
        )

    system = (
        "You are a political media analyst. Given 24h sentiment metrics for one politician, "
        "write a concise brief. Reply ONLY as JSON: "
        '{"summary": "2-3 sentences", "actions": ["action1", "action2", "action3"]}. '
        "Actions must be concrete and specific to the data."
    )
    user = json.dumps(ctx)
    raw = llm.complete(system, user, max_tokens=400)

    summary, actions = _parse_brief(raw, ctx)
    brief = Brief(
        politician_id=politician_id,
        summary=summary,
        actions=actions,
        generated_at=now_ist().isoformat(),
    )
    cache_set(
        cache_key,
        {
            "politician_id": brief.politician_id,
            "summary": brief.summary,
            "actions": brief.actions,
            "generated_at": brief.generated_at,
        },
        ttl=86400,
    )
    log.info("ai_brief_generated", politician_id=politician_id, topics=ctx.get("top_topics"))
    return brief


def _parse_brief(raw: str, ctx: dict) -> tuple[str, list[str]]:
    """Parse the LLM JSON; fall back to a data-driven brief if it isn't valid JSON."""
    try:
        data = json.loads(raw)
        summary = str(data["summary"])
        actions = [str(a) for a in data.get("actions", [])][:5]
        if summary:
            return summary, actions
    except (json.JSONDecodeError, KeyError, TypeError):
        pass
    # Deterministic fallback so the brief is never empty.
    topics = ", ".join(ctx.get("top_topics", [])) or "no dominant topics"
    spike_note = " An active spike is in progress." if ctx.get("active_spike") else ""
    neg = ctx.get("negative_24h")
    pos = ctx.get("positive_24h")
    summary = (
        f"Latest sentiment score is {ctx.get('latest_score')}/100 with "
        f"{neg} negative vs {pos} positive mentions in 24h. "
        f"Top concerns: {topics}.{spike_note}"
    )
    actions = [
        "Review the most negative topic and prepare a public response.",
        "Schedule a visit or statement addressing the top concern.",
        (
            "Monitor the spike for the next 24 hours."
            if ctx.get("active_spike")
            else "Maintain current engagement cadence."
        ),
    ]
    return summary, actions
