"""X (Twitter) client via SocialData.tools (WP9).

Free real-time X data does not exist; SocialData.tools is a paid provider.
`FakeSocialDataClient` powers offline/demo; `RealSocialDataClient` is the live
wiring point. Results land in the unified `mentions` table (platform="x").
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.clients.resilient import ExternalServiceError, resilient_call
from app.config import Settings, get_settings
from app.core.timezone import now_ist


@dataclass
class XMention:
    platform_id: str
    text: str
    author: str
    created_at: datetime
    likes: int


class SocialDataClient(Protocol):
    def search(self, query: str) -> list[XMention]: ...


class FakeSocialDataClient:
    """Deterministic demo X mentions."""

    _SAMPLES = [
        "{q} did great work on the metro project 👏",
        "still waiting on {q} to fix the water supply, frustrating",
        "{q} press conference today was solid",
        "corruption allegations against {q} trending again",
    ]

    def search(self, query: str) -> list[XMention]:
        out: list[XMention] = []
        for i, tmpl in enumerate(self._SAMPLES):
            seed = f"x:{query}:{i}"
            h = int(hashlib.sha256(seed.encode()).hexdigest(), 16)
            out.append(
                XMention(
                    platform_id=f"x_{seed}",
                    text=tmpl.format(q=query.lstrip("@")),
                    author=f"@user{h % 9999}",
                    created_at=now_ist(),
                    likes=h % 500,
                )
            )
        return out


class RealSocialDataClient:
    """Live SocialData.tools client (paid)."""

    def __init__(self, settings: Settings) -> None:
        self._key = settings.socialdata_api_key.get_secret_value()

    def search(self, query: str) -> list[XMention]:
        if not self._key:
            return []

        def _call() -> list[XMention]:
            import httpx

            try:
                resp = httpx.get(
                    "https://api.socialdata.tools/twitter/search",
                    params={"query": query, "type": "Latest"},
                    headers={"Authorization": f"Bearer {self._key}"},
                    timeout=30,
                )
            except httpx.HTTPError as exc:
                raise ExternalServiceError(f"transport: {exc}") from exc
            if resp.status_code >= 400:
                raise ExternalServiceError(f"http {resp.status_code}: {resp.text[:200]}")
            tweets = resp.json().get("tweets", [])  # VERIFY shape vs SocialData docs
            out: list[XMention] = []
            for t in tweets:
                out.append(
                    XMention(
                        platform_id=str(t.get("id_str") or t.get("id")),
                        text=t.get("full_text") or t.get("text", ""),
                        author=str(t.get("user", {}).get("screen_name", "")),
                        created_at=now_ist(),
                        likes=int(t.get("favorite_count", 0)),
                    )
                )
            return out

        return resilient_call(_call, default=[], op="socialdata.search")


def get_socialdata_client(settings: Settings | None = None) -> SocialDataClient:
    settings = settings or get_settings()
    if settings.use_fake_clients or not settings.socialdata_api_key.get_secret_value():
        return FakeSocialDataClient()
    return RealSocialDataClient(settings)
