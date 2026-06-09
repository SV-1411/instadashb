"""Google Natural Language API client (WP8 comment sentiment).

`GoogleNlClient` returns a -1..1 sentiment for a piece of text. `FakeGoogleNlClient`
(offline/tests) reuses the demo lexicon. `RealGoogleNlClient` calls the live
`documents:analyzeSentiment` REST endpoint with an API key; the HTTP call is wrapped
in ``resilient_call`` and returns ``None`` if the API is unavailable so the caller
can fall back to the lexicon (rule 3: never crash a cycle).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from app.clients.resilient import ExternalServiceError, resilient_call
from app.config import Settings, get_settings
from app.services.sentiment_reactions import classify_comment

_NL_URL = "https://language.googleapis.com/v1/documents:analyzeSentiment"


@dataclass
class NlSentiment:
    score: float  # -1..1
    magnitude: float  # 0..inf (strength of emotion)
    language: str | None


class GoogleNlClient(Protocol):
    def analyze_sentiment(self, text: str) -> NlSentiment | None: ...


class FakeGoogleNlClient:
    """Deterministic offline NL using the demo lexicon (same -1..1 contract)."""

    def analyze_sentiment(self, text: str) -> NlSentiment | None:
        score, _label = classify_comment(text)
        return NlSentiment(score=score, magnitude=abs(score), language="en")


class RealGoogleNlClient:
    """Live Google NL API client (API-key auth)."""

    def __init__(self, settings: Settings) -> None:
        self._key = settings.google_nl_api_key.get_secret_value()

    def analyze_sentiment(self, text: str) -> NlSentiment | None:
        if not self._key or not text.strip():
            return None

        def _call() -> NlSentiment | None:
            body = {
                "document": {"type": "PLAIN_TEXT", "content": text},
                "encodingType": "UTF8",
            }
            try:
                resp = httpx.post(_NL_URL, params={"key": self._key}, json=body, timeout=15)
            except httpx.HTTPError as exc:
                raise ExternalServiceError(f"transport: {exc}") from exc
            if resp.status_code >= 400:
                # Unsupported language / bad request -> let caller fall back to lexicon.
                raise ExternalServiceError(f"http {resp.status_code}: {resp.text[:200]}")
            data: dict[str, Any] = resp.json()
            ds = data.get("documentSentiment", {})
            return NlSentiment(
                score=float(ds.get("score", 0.0)),
                magnitude=float(ds.get("magnitude", 0.0)),
                language=data.get("language"),
            )

        return resilient_call(_call, default=None, op="google_nl.analyze_sentiment")


def get_google_nl_client(settings: Settings | None = None) -> GoogleNlClient:
    """Factory: Fake in demo/test mode or when no key is set, else the live client."""
    settings = settings or get_settings()
    if settings.use_fake_clients or not settings.google_nl_api_key.get_secret_value():
        return FakeGoogleNlClient()
    return RealGoogleNlClient(settings)
