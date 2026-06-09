"""Misinformation signal (WP10): a claim-volume flag.

We can't fact-check, but we CAN flag when claim/rumor-style chatter spikes in
volume — a cue for the team to investigate. Detection is keyword-based over a
recent window, grouped by topic, flagged when volume crosses a threshold.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.timezone import floor_to_hour_ist, now_ist
from app.models.mention import Mention

# Phrases that often signal a circulating claim/rumor (en + hi/mr romanized).
CLAIM_KEYWORDS = (
    "fake",
    "rumor",
    "rumour",
    "false",
    "fake news",
    "viral video",
    "hoax",
    "misleading",
    "afwah",
    "अफवाह",
    "खोटी",
    "fake photo",
    "edited video",
    "propaganda",
)

CLAIM_VOLUME_THRESHOLD = 5  # mentions in the window to raise a flag


@dataclass
class MisinfoFlag:
    flagged: bool
    claim_volume: int
    window_hours: int
    sample_texts: list[str]


def detect_misinformation(db: Session, politician_id: int, hours: int = 24) -> MisinfoFlag:
    """Count claim-style mentions in the recent window; flag if over threshold."""
    since = floor_to_hour_ist(now_ist()) - timedelta(hours=hours)
    rows = (
        db.execute(
            select(Mention).where(
                Mention.politician_id == politician_id,
                Mention.raw_text.is_not(None),
                Mention.platform_ts >= since,
            )
        )
        .scalars()
        .all()
    )

    hits = [
        m.raw_text
        for m in rows
        if m.raw_text and any(kw in m.raw_text.lower() for kw in CLAIM_KEYWORDS)
    ]
    return MisinfoFlag(
        flagged=len(hits) >= CLAIM_VOLUME_THRESHOLD,
        claim_volume=len(hits),
        window_hours=hours,
        sample_texts=[t for t in hits[:5] if t],
    )
