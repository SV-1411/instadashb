"""Reaction + comment sentiment unit tests (no DB)."""

from __future__ import annotations

from app.services.sentiment_reactions import (
    classify_comment,
    label_from_score,
    reaction_ratio_score,
)


def test_reaction_ratio_all_positive() -> None:
    assert reaction_ratio_score({"like": 80, "love": 20}) == 1.0


def test_reaction_ratio_all_negative() -> None:
    assert reaction_ratio_score({"angry": 30, "sad": 10}) == -1.0


def test_reaction_ratio_empty_is_zero() -> None:
    assert reaction_ratio_score({}) == 0.0


def test_classify_comment_labels() -> None:
    pos_score, pos_label = classify_comment("great work, proud of you")
    neg_score, neg_label = classify_comment("worst corruption, shame")
    neu_score, neu_label = classify_comment("when is the next event")
    assert pos_label == "positive" and pos_score > 0
    assert neg_label == "negative" and neg_score < 0
    assert neu_label == "neutral" and neu_score == 0.0


def test_label_thresholds() -> None:
    assert label_from_score(0.5) == "positive"
    assert label_from_score(-0.5) == "negative"
    assert label_from_score(0.0) == "neutral"
