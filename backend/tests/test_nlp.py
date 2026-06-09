"""WP8 NLP tests: sampling gate, Google-NL-vs-lexicon routing, live parsing, batch."""

from __future__ import annotations

import httpx
import respx
from app.clients.google_nl import (
    FakeGoogleNlClient,
    GoogleNlClient,
    NlSentiment,
    RealGoogleNlClient,
)
from app.config import Settings
from app.models.mention import Mention
from app.models.politician import Politician
from app.services.nlp import process_nlp_batch, sample_in, score_text
from sqlalchemy.orm import Session

NL_URL = "https://language.googleapis.com/v1/documents:analyzeSentiment"


def test_sample_in_bounds_and_determinism() -> None:
    assert sample_in("anything", 1.0) is True
    assert sample_in("anything", 0.0) is False
    # Deterministic: same key -> same decision.
    assert sample_in("comment_42", 0.5) == sample_in("comment_42", 0.5)


def test_score_text_uses_google_nl_when_sampled_in() -> None:
    s = Settings(nlp_sample_rate=1.0)
    res = score_text("great work, proud", "k1", FakeGoogleNlClient(), s)
    assert res.source == "google_nl"
    assert res.label == "positive"


def test_score_text_falls_back_to_lexicon_when_unavailable() -> None:
    class _NoneClient:
        def analyze_sentiment(self, text: str) -> NlSentiment | None:
            return None

    s = Settings(nlp_sample_rate=1.0)
    res = score_text("corruption shame", "k2", _NoneClient(), s)
    assert res.source == "lexicon"
    assert res.label == "negative"


def test_score_text_sampled_out_uses_lexicon() -> None:
    s = Settings(nlp_sample_rate=0.0)  # nothing sampled in
    res = score_text("great work", "k3", FakeGoogleNlClient(), s)
    assert res.source == "lexicon"


def test_real_client_no_key_returns_none() -> None:
    assert RealGoogleNlClient(Settings(google_nl_api_key="")).analyze_sentiment("hi") is None


@respx.mock
def test_real_client_parses_sentiment() -> None:
    respx.post(NL_URL).mock(
        return_value=httpx.Response(
            200,
            json={"documentSentiment": {"score": 0.8, "magnitude": 1.2}, "language": "en"},
        )
    )
    nl = RealGoogleNlClient(Settings(google_nl_api_key="k")).analyze_sentiment("good")
    assert nl is not None
    assert nl.score == 0.8
    assert nl.language == "en"


def test_process_nlp_batch_marks_processed(db_session: Session) -> None:
    pol = Politician(name="NLP Demo")
    db_session.add(pol)
    db_session.commit()
    db_session.refresh(pol)

    for i, text in enumerate(["great work", "corruption shame", "namaste"]):
        db_session.add(
            Mention(
                politician_id=pol.id,
                platform="ig",
                source_type="comment",
                platform_mention_id=f"m{i}",
                raw_text=text,
                language="en",
                sentiment_score=0.0,
                sentiment_label="neutral",
                topics=[],
                likes_count=0,
                processed=False,
            )
        )
    db_session.commit()

    client: GoogleNlClient = FakeGoogleNlClient()
    n = process_nlp_batch(
        db_session, client, politician_id=pol.id, settings=Settings(nlp_sample_rate=1.0)
    )
    assert n == 3

    rows = db_session.query(Mention).filter_by(politician_id=pol.id).all()
    assert all(m.processed is True for m in rows)
    labels = {m.raw_text: m.sentiment_label for m in rows}
    assert labels["great work"] == "positive"
    assert labels["corruption shame"] == "negative"
