"""LLM client (OpenRouter, OpenAI-compatible) for topic extraction + AI Brief.

`FakeLlmClient` returns deterministic canned completions (offline/tests).
`OpenRouterLlmClient` calls OpenRouter's `/chat/completions` (works with any model,
including free ones). The HTTP call is wrapped in ``resilient_call`` and returns ""
on failure so callers degrade gracefully (rule 3).
"""

from __future__ import annotations

from typing import Any, Protocol

import httpx

from app.clients.resilient import ExternalServiceError, resilient_call
from app.config import Settings, get_settings


class LlmClient(Protocol):
    def complete(self, system: str, user: str, *, max_tokens: int = 600) -> str: ...


class FakeLlmClient:
    """Deterministic offline LLM. Echoes a compact, useful canned response so the
    topic + brief pipelines run without network."""

    def complete(self, system: str, user: str, *, max_tokens: int = 600) -> str:
        low = user.lower()
        if "extract topics" in system.lower() or "topics" in system.lower():
            # Topic-extraction prompt -> return a JSON array of topics from keywords seen.
            topics = []
            for kw, topic in (
                ("road", "roads"),
                ("water", "water"),
                ("corrupt", "corruption"),
                ("job", "employment"),
                ("rally", "events"),
                ("health", "healthcare"),
            ):
                if kw in low:
                    topics.append(topic)
            return '{"topics": ' + str(topics).replace("'", '"') + "}"
        # AI Brief prompt -> a short canned brief.
        return (
            "Sentiment is mixed with a recent negative spike. Top concerns: roads and water. "
            "Recommended actions: (1) issue a statement on the road repair timeline, "
            "(2) schedule a ward visit in the most negative city, (3) monitor the spike for 24h."
        )


class OpenRouterLlmClient:
    """Live OpenRouter client (OpenAI-compatible chat completions)."""

    def __init__(self, settings: Settings) -> None:
        self._key = settings.openrouter_api_key.get_secret_value()
        self._base = settings.openrouter_base_url.rstrip("/")
        self._model = settings.openrouter_model

    def complete(self, system: str, user: str, *, max_tokens: int = 600) -> str:
        if not self._key:
            return ""

        def _call() -> str:
            headers = {
                "Authorization": f"Bearer {self._key}",
                "HTTP-Referer": "https://civicpulse.local",  # OpenRouter attribution (optional)
                "X-Title": "CivicPulse",
            }
            body: dict[str, Any] = {
                "model": self._model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "max_tokens": max_tokens,
                "temperature": 0.3,
            }
            try:
                resp = httpx.post(
                    f"{self._base}/chat/completions", headers=headers, json=body, timeout=60
                )
            except httpx.HTTPError as exc:
                raise ExternalServiceError(f"transport: {exc}") from exc
            if resp.status_code >= 400:
                raise ExternalServiceError(f"http {resp.status_code}: {resp.text[:200]}")
            data = resp.json()
            return str(data["choices"][0]["message"]["content"])

        return resilient_call(_call, default="", op="openrouter.complete")


def get_llm_client(settings: Settings | None = None) -> LlmClient:
    """Factory: Fake in demo/test mode or when no key is set, else OpenRouter."""
    settings = settings or get_settings()
    if settings.use_fake_clients or not settings.openrouter_api_key.get_secret_value():
        return FakeLlmClient()
    return OpenRouterLlmClient(settings)
