"""Reaction-ratio sentiment (WP3) — no NLP yet (that's WP8).

Two signals:
- `reaction_ratio_score`: from FB reaction counts (love/like/haha/wow vs angry/sad).
- `classify_comment`: a lightweight lexicon scorer standing in for the Google NL API
  until WP8 (kept behind the same -1..1 / label contract so WP8 is a drop-in swap).
"""

from __future__ import annotations

POSITIVE_REACTIONS = ("like", "love", "haha", "wow")
NEGATIVE_REACTIONS = ("angry", "sad")

# Tiny demo lexicon (Hindi/Marathi/English) — replaced by Google NL API in WP8.
_POS_WORDS = {"great", "well", "done", "proud", "best", "thank", "good", "badhai", "chhan"}
_NEG_WORDS = {"worst", "corruption", "shame", "nothing", "fail", "bekar", "vaeet", "ghotala"}


def reaction_ratio_score(reactions: dict[str, int]) -> float:
    """Return a -1..1 sentiment from reaction counts. 0 when there are none."""
    pos = sum(reactions.get(k, 0) for k in POSITIVE_REACTIONS)
    neg = sum(reactions.get(k, 0) for k in NEGATIVE_REACTIONS)
    total = pos + neg
    if total == 0:
        return 0.0
    return round((pos - neg) / total, 4)


def classify_comment(text: str) -> tuple[float, str]:
    """Return (score in -1..1, label) for a comment using the demo lexicon."""
    words = {w.strip(".,!?").lower() for w in text.split()}
    pos = len(words & _POS_WORDS)
    neg = len(words & _NEG_WORDS)
    if pos == 0 and neg == 0:
        return 0.0, "neutral"
    score = round((pos - neg) / (pos + neg), 4)
    return score, label_from_score(score)


def label_from_score(score: float) -> str:
    """Map a -1..1 score to a sentiment label (shared threshold everywhere)."""
    if score > 0.15:
        return "positive"
    if score < -0.15:
        return "negative"
    return "neutral"
