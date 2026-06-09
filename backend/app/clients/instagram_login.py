"""Instagram API with Instagram Login (graph.instagram.com) — no Facebook Page.

Implements the same MetaClient interface as the Facebook-Page client, but talks to
`graph.instagram.com` with an Instagram User token. This is Meta's newer path that
lets an IG Business/Creator account be used directly, without a linked FB Page.

Endpoints used (stable Instagram Graph fields; spots to re-verify marked # VERIFY):
  GET /me?fields=user_id,username,account_type
  GET /me/media?fields=id,caption,media_type,timestamp,like_count,comments_count,
      comments{id,text,timestamp,username,like_count}
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from app.clients.meta import AudienceCity, RawComment, RawPost, TokenHealth
from app.clients.resilient import ExternalServiceError, resilient_call
from app.config import Settings
from app.core.logging import get_logger
from app.core.timezone import now_ist

log = get_logger("clients.instagram_login")

IG_BASE = "https://graph.instagram.com"


def ig_get(path: str, params: dict[str, Any]) -> dict[str, Any]:
    """One graph.instagram.com GET. Raises ExternalServiceError on any error."""
    try:
        resp = httpx.get(f"{IG_BASE}/{path}", params=params, timeout=15)
    except httpx.HTTPError as exc:
        raise ExternalServiceError(f"transport: {exc}") from exc
    if resp.status_code >= 400:
        raise ExternalServiceError(f"http {resp.status_code}: {resp.text[:200]}")
    data: dict[str, Any] = resp.json()
    return data


class InstagramLoginClient:
    """Live Instagram-Login client. Used when META_SOURCE=instagram_login."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def token_health(self, token: str | None) -> TokenHealth:
        if not token:
            return TokenHealth(status="missing", detail="No token stored")

        def _check() -> TokenHealth:
            try:
                ig_get("me", {"access_token": token, "fields": "user_id,username"})
                return TokenHealth(status="connected")
            except ExternalServiceError as exc:
                if "400" in str(exc) or "OAuthException" in str(exc):
                    return TokenHealth(status="expired", detail="Token expired/invalid")
                raise

        return resilient_call(
            _check,
            default=TokenHealth(status="expired", detail="health check failed"),
            op="ig_login.token_health",
        )

    def get_posts(self, account_id: str, token: str | None, since: datetime) -> list[RawPost]:
        if not token:
            return []

        def _fetch() -> list[RawPost]:
            # Fetch the latest posts (newest first); dedupe makes re-fetches cheap.
            # We intentionally don't filter by `since` — accounts post irregularly.
            data = ig_get(
                "me/media",
                {
                    "fields": (
                        "id,caption,media_type,timestamp,like_count,comments_count,"
                        "comments{id,text,timestamp,username,like_count}"
                    ),
                    "limit": 50,
                    "access_token": token,
                },
            )
            return [_parse_media(item) for item in data.get("data", [])]

        return resilient_call(_fetch, default=[], op="ig_login.get_posts")

    def get_audience_geo(self, account_id: str, token: str | None) -> list[AudienceCity]:
        if not token:
            return []

        def _fetch() -> list[AudienceCity]:
            # VERIFY: follower_demographics availability depends on follower count (>=100).
            data = ig_get(
                "me/insights",
                {
                    "metric": "follower_demographics",
                    "period": "lifetime",
                    "metric_type": "total_value",
                    "breakdown": "city",
                    "access_token": token,
                },
            )
            return _parse_audience(data)

        return resilient_call(_fetch, default=[], op="ig_login.get_audience_geo")


def _parse_media(item: dict[str, Any]) -> RawPost:
    ts = item.get("timestamp")
    created = datetime.fromisoformat(ts.replace("Z", "+00:00")) if ts else now_ist()
    comments = []
    for c in item.get("comments", {}).get("data", []):
        cts = c.get("timestamp")
        comments.append(
            RawComment(
                platform_id=str(c.get("id")),
                text=c.get("text", ""),
                language="und",
                likes=int(c.get("like_count", 0)),
                created_at=datetime.fromisoformat(cts.replace("Z", "+00:00")) if cts else created,
            )
        )
    return RawPost(
        platform_id=str(item.get("id")),
        platform="ig",
        reach=0,  # per-media insights are a separate call; add later if needed
        impressions=0,
        likes=int(item.get("like_count", 0)),
        comments_count=int(item.get("comments_count", 0)),
        shares=0,
        saves=0,
        reactions={},
        comments=comments,
        created_at=created,
    )


def _parse_audience(data: dict[str, Any]) -> list[AudienceCity]:
    out: list[AudienceCity] = []
    try:
        values = data["data"][0]["total_value"]["breakdowns"][0]["results"]
        total = sum(int(r["value"]) for r in values) or 1
        for r in values:
            out.append(
                AudienceCity(
                    city=r["dimension_values"][0],
                    follower_pct=round(int(r["value"]) / total * 100, 1),
                    age_band="all",
                    gender="all",
                )
            )
    except (KeyError, IndexError, TypeError):
        log.warning("ig_audience_parse_unexpected_shape")
    return out
