"""Topic extraction (WP9): a multilingual keyword dictionary (Hindi/Marathi/English)
plus optional LLM extraction for comments the dictionary misses. Topics are stored
on `mentions.topics` and rolled up into `aggregates.top_topics`."""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clients.llm import LlmClient
from app.core.logging import get_logger
from app.core.timezone import floor_to_hour_ist, now_ist
from app.models.mention import Mention

log = get_logger("services.topics")

# topic -> trigger keywords (lowercased). Devanagari + romanized + English.
TOPIC_DICTIONARY: dict[str, list[str]] = {
    "roads": ["road", "roads", "रोड", "सड़क", "रस्ता", "rasta", "pothole", "गड्ढे"],
    "water": ["water", "पानी", "पाणी", "supply", "नल", "tanker"],
    "electricity": ["electricity", "power", "बिजली", "वीज", "load shedding", "outage"],
    "corruption": ["corruption", "भ्रष्टाचार", "ghotala", "घोटाळा", "bribe", "रिश्वत", "scam"],
    "employment": ["job", "jobs", "नौकरी", "रोजगार", "employment", "unemployment", "बेरोजगारी"],
    "healthcare": ["hospital", "health", "अस्पताल", "रुग्णालय", "doctor", "dengue", "clinic"],
    "education": ["school", "college", "शिक्षा", "शाळा", "education", "students"],
    "events": ["rally", "रैली", "सभा", "event", "visit", "दौरा", "speech", "yatra"],
    "safety": ["crime", "safety", "अपराध", "police", "सुरक्षा", "theft"],
}


def dictionary_topics(text: str) -> list[str]:
    """Match topics by keyword. Returns a de-duplicated, ordered list."""
    low = (text or "").lower()
    found: list[str] = []
    for topic, keywords in TOPIC_DICTIONARY.items():
        if any(kw in low for kw in keywords):
            found.append(topic)
    return found


def llm_topics(text: str, llm: LlmClient) -> list[str]:
    """Ask the LLM for topics when the dictionary finds none. Returns [] on any error."""
    system = (
        "You extract civic/political topics from a social media comment. "
        'Reply ONLY with JSON: {"topics": ["topic1", "topic2"]}. '
        "Use short lowercase English nouns. Max 3 topics. No prose."
    )
    raw = llm.complete(system, text, max_tokens=80)
    try:
        data = json.loads(raw)
        topics = data.get("topics", [])
        return [str(t).lower().strip() for t in topics if str(t).strip()][:3]
    except (json.JSONDecodeError, AttributeError, TypeError):
        return []


def assign_topics_recent(
    db: Session,
    politician_id: int,
    llm: LlmClient | None = None,
    hours: int = 48,
    use_llm: bool = True,
) -> int:
    """Assign topics to recent mentions that have none yet. Dictionary first;
    LLM only for the ones the dictionary can't classify (keeps LLM cost low)."""
    since = floor_to_hour_ist(now_ist()).replace(hour=0)  # start of recent window day
    _ = hours  # window kept simple for the demo; recent untagged mentions only
    mentions = (
        db.execute(
            select(Mention).where(
                Mention.politician_id == politician_id,
                Mention.topics == [],
                Mention.raw_text.is_not(None),
                Mention.platform_ts >= since,
            )
        )
        .scalars()
        .all()
    )

    updated = 0
    for m in mentions:
        topics = dictionary_topics(m.raw_text or "")
        if not topics and use_llm and llm is not None:
            topics = llm_topics(m.raw_text or "", llm)
        if topics:
            m.topics = topics
            updated += 1
    db.commit()
    log.info("topics_assigned", politician_id=politician_id, updated=updated)
    return updated
