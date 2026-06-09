"""Scraper supplement client — broad public Instagram chatter the official API
can't see (untagged mentions, hashtags, keyword search).

Provider-agnostic: `ScraperClient` interface + `FakeScraperClient` (demo/tests) +
`ApifyScraperClient` (live wiring point). Results flow into the unified `mentions`
table as ``source_type="mention"`` so they share the sentiment/aggregate/spike path.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.config import Settings, get_settings
from app.core.timezone import now_ist


@dataclass
class ScrapedMention:
    platform_id: str
    text: str
    author: str
    created_at: datetime
    likes: int
    url: str


class ScraperClient(Protocol):
    def search(self, queries: list[str]) -> list[ScrapedMention]: ...


class FakeScraperClient:
    """Deterministic demo chatter for offline mode + tests."""

    _SAMPLES = [
        "heard {q} is doing great work in the city",
        "{q} did nothing about the water problem, shame",
        "anyone going to the {q} rally tomorrow?",
        "{q} corruption news is trending again",
        "proud of {q} for the new road project",
    ]

    def search(self, queries: list[str]) -> list[ScrapedMention]:
        out: list[ScrapedMention] = []
        for q in queries:
            for i, tmpl in enumerate(self._SAMPLES):
                seed = f"{q}:{i}"
                h = int(hashlib.sha256(seed.encode()).hexdigest(), 16)
                out.append(
                    ScrapedMention(
                        platform_id=f"scrape_{seed}",
                        text=tmpl.format(q=q.lstrip("@#")),
                        author=f"user_{h % 9999}",
                        created_at=now_ist(),
                        likes=h % 120,
                        url=f"https://instagram.com/p/{h % 10**8}",
                    )
                )
        return out


class ApifyScraperClient:
    """Live Apify-backed scraper. Wired once SCRAPER_API_KEY is set.

    Apify runs an 'actor' (e.g. an Instagram hashtag/comment scraper), then you poll
    its dataset for results. That run+poll flow goes here.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def search(self, queries: list[str]) -> list[ScrapedMention]:
        raise NotImplementedError(
            "ApifyScraperClient needs SCRAPER_API_KEY + an actor id. See docs/CONNECT_INSTAGRAM.md."
        )


def get_scraper_client(settings: Settings | None = None) -> ScraperClient:
    settings = settings or get_settings()
    if settings.use_fake_clients or settings.scraper_provider == "fake":
        return FakeScraperClient()
    if settings.scraper_provider == "apify":
        return ApifyScraperClient(settings)
    # Unknown provider -> safe fake (worker logs the misconfig elsewhere).
    return FakeScraperClient()
