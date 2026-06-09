"""Meta (Instagram/Facebook) client + OAuth helpers.

`MetaClient` is the interface the ingestion service depends on. `FakeMetaClient`
returns deterministic demo data (offline mode + tests). `RealMetaClient` calls the
live Graph API via httpx, every call wrapped in ``resilient_call`` so a transient
upstream failure degrades gracefully instead of crashing a cycle (rule 3).

OAuth (module-level helpers `build_oauth_url` / `exchange_code_for_token` /
`exchange_for_long_lived` / `discover_ig_account`) powers the one-time connect flow
in ``app/api/auth_meta.py``.

NOTE: Graph API field/scope/metric names drift over time. Spots that need
verification against the current Meta docs are marked `# VERIFY`.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Protocol

import httpx

from app.clients.resilient import ExternalServiceError, resilient_call
from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.core.timezone import now_ist

log = get_logger("clients.meta")


@dataclass
class RawComment:
    platform_id: str
    text: str
    language: str
    likes: int
    created_at: datetime


@dataclass
class RawPost:
    platform_id: str
    platform: str  # "ig" | "fb"
    reach: int
    impressions: int
    likes: int
    comments_count: int
    shares: int
    saves: int
    reactions: dict[str, int] = field(default_factory=dict)
    comments: list[RawComment] = field(default_factory=list)
    created_at: datetime = field(default_factory=now_ist)


@dataclass
class TokenHealth:
    status: str  # "connected" | "expired" | "revoked" | "missing"
    detail: str | None = None


@dataclass
class AudienceCity:
    city: str
    follower_pct: float
    age_band: str
    gender: str


class MetaClient(Protocol):
    """What the ingestion service needs from Meta — nothing more. Every method
    takes the per-politician access token (Fake ignores it)."""

    def token_health(self, token: str | None) -> TokenHealth: ...
    def get_posts(self, account_id: str, token: str | None, since: datetime) -> list[RawPost]: ...
    def get_audience_geo(self, account_id: str, token: str | None) -> list[AudienceCity]: ...


# ── Fake implementation (deterministic; used in tests + offline demo) ────────

_POSITIVE = ["great work", "well done sir", "proud of you", "best leader", "thank you"]
_NEGATIVE = ["worst roads", "nothing changed", "corruption everywhere", "shame", "do your job"]
_NEUTRAL = ["when is the next event", "please visit our area", "info needed", "namaste"]


def _seeded_int(seed: str, lo: int, hi: int) -> int:
    """Deterministic pseudo-random int from a string seed."""
    h = int(hashlib.sha256(seed.encode()).hexdigest(), 16)
    return lo + (h % (hi - lo + 1))


class FakeMetaClient:
    """Generates realistic, deterministic demo posts/comments/audience."""

    def __init__(self, posts_per_cycle: int = 5, negativity: float = 0.25) -> None:
        self.posts_per_cycle = posts_per_cycle
        self.negativity = negativity

    def token_health(self, token: str | None) -> TokenHealth:
        if not token:
            return TokenHealth(status="missing", detail="No token stored")
        return TokenHealth(status="connected")

    def get_posts(self, account_id: str, token: str | None, since: datetime) -> list[RawPost]:
        posts: list[RawPost] = []
        for i in range(self.posts_per_cycle):
            seed = f"{account_id}:{since.isoformat()}:{i}"
            n_comments = _seeded_int(seed + "c", 3, 12)
            comments: list[RawComment] = []
            for j in range(n_comments):
                cseed = f"{seed}:{j}"
                roll = _seeded_int(cseed, 0, 99)
                if roll < self.negativity * 100:
                    text = _NEGATIVE[_seeded_int(cseed, 0, len(_NEGATIVE) - 1)]
                elif roll < self.negativity * 100 + 35:
                    text = _NEUTRAL[_seeded_int(cseed, 0, len(_NEUTRAL) - 1)]
                else:
                    text = _POSITIVE[_seeded_int(cseed, 0, len(_POSITIVE) - 1)]
                comments.append(
                    RawComment(
                        platform_id=f"cmt_{cseed}",
                        text=text,
                        language="en",
                        likes=_seeded_int(cseed + "l", 0, 50),
                        created_at=since + timedelta(minutes=j),
                    )
                )
            posts.append(
                RawPost(
                    platform_id=f"post_{seed}",
                    platform="ig" if i % 2 == 0 else "fb",
                    reach=_seeded_int(seed + "r", 1000, 50000),
                    impressions=_seeded_int(seed + "im", 1500, 80000),
                    likes=_seeded_int(seed + "lk", 50, 5000),
                    comments_count=n_comments,
                    shares=_seeded_int(seed + "sh", 0, 800),
                    saves=_seeded_int(seed + "sv", 0, 400),
                    reactions={
                        "like": _seeded_int(seed + "rl", 50, 3000),
                        "love": _seeded_int(seed + "rlv", 10, 1500),
                        "haha": _seeded_int(seed + "rh", 0, 300),
                        "wow": _seeded_int(seed + "rw", 0, 200),
                        "sad": _seeded_int(seed + "rs", 0, 400),
                        "angry": _seeded_int(seed + "ra", 0, 600),
                    },
                    comments=comments,
                    created_at=since,
                )
            )
        return posts

    def get_audience_geo(self, account_id: str, token: str | None) -> list[AudienceCity]:
        cities = ["Pune", "Mumbai", "Nagpur", "Nashik", "Aurangabad", "Thane"]
        return [
            AudienceCity(
                city=c,
                follower_pct=round(_seeded_int(account_id + c, 5, 30) + 0.0, 1),
                age_band="25-34",
                gender="mixed",
            )
            for c in cities
        ]


# ── OAuth + Graph helpers (module-level; used by the connect flow) ───────────


def _graph_base() -> str:
    return f"https://graph.facebook.com/{get_settings().meta_graph_api_version}"


def build_oauth_url(state: str) -> str:
    """The URL we redirect the account owner to, to grant our app access."""
    s = get_settings()
    ver = s.meta_graph_api_version
    params = httpx.QueryParams(
        {
            "client_id": s.meta_app_id,
            "redirect_uri": s.meta_oauth_redirect_uri,
            "state": state,
            "scope": s.meta_scopes,
            "response_type": "code",
        }
    )
    return f"https://www.facebook.com/{ver}/dialog/oauth?{params}"


def _graph_get(path: str, params: dict[str, Any]) -> dict[str, Any]:
    """One Graph GET. Raises ExternalServiceError on any transport/HTTP/API error."""
    try:
        resp = httpx.get(f"{_graph_base()}/{path}", params=params, timeout=15)
    except httpx.HTTPError as exc:
        raise ExternalServiceError(f"transport: {exc}") from exc
    if resp.status_code >= 400:
        raise ExternalServiceError(f"http {resp.status_code}: {resp.text[:200]}")
    data: dict[str, Any] = resp.json()
    return data


def exchange_code_for_token(code: str) -> str:
    """Exchange the OAuth ``code`` for a short-lived access token."""
    s = get_settings()
    data = _graph_get(
        "oauth/access_token",
        {
            "client_id": s.meta_app_id,
            "client_secret": s.meta_app_secret.get_secret_value(),
            "redirect_uri": s.meta_oauth_redirect_uri,
            "code": code,
        },
    )
    return str(data["access_token"])


def exchange_for_long_lived(short_token: str) -> str:
    """Upgrade a short-lived token to a ~60-day long-lived token."""
    s = get_settings()
    data = _graph_get(
        "oauth/access_token",
        {
            "grant_type": "fb_exchange_token",
            "client_id": s.meta_app_id,
            "client_secret": s.meta_app_secret.get_secret_value(),
            "fb_exchange_token": short_token,
        },
    )
    return str(data["access_token"])


def discover_ig_account(token: str) -> dict[str, str]:
    """Find the IG Business account id + Page id behind a user token."""
    data = _graph_get(
        "me/accounts",
        {"fields": "name,id,instagram_business_account", "access_token": token},  # VERIFY fields
    )
    for page in data.get("data", []):
        iba = page.get("instagram_business_account")
        if iba and iba.get("id"):
            return {"page_id": str(page["id"]), "ig_user_id": str(iba["id"])}
    raise ExternalServiceError("No Instagram Business account linked to any Page on this login.")


# ── Real implementation (live Graph API) ─────────────────────────────────────


class RealMetaClient:
    """Live Meta Graph API client. Used when USE_FAKE_CLIENTS=false."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def token_health(self, token: str | None) -> TokenHealth:
        if not token:
            return TokenHealth(status="missing", detail="No token stored")

        def _check() -> TokenHealth:
            try:
                _graph_get("me", {"access_token": token, "fields": "id"})
                return TokenHealth(status="connected")
            except ExternalServiceError as exc:
                # Graph error code 190 == token expired/revoked.
                msg = str(exc)
                if "190" in msg or "OAuthException" in msg:
                    return TokenHealth(status="expired", detail="Token expired or revoked (190)")
                raise

        return resilient_call(
            _check,
            default=TokenHealth(status="expired", detail="health check failed"),
            op="meta.token_health",
        )

    def get_posts(self, account_id: str, token: str | None, since: datetime) -> list[RawPost]:
        if not token:
            return []

        def _fetch() -> list[RawPost]:
            data = _graph_get(
                f"{account_id}/media",
                {
                    # VERIFY fields against current IG Graph docs.
                    "fields": (
                        "id,caption,like_count,comments_count,timestamp,media_type,"
                        "comments{id,text,timestamp,like_count}"
                    ),
                    "limit": 50,
                    "access_token": token,
                },
            )
            return [_parse_ig_media(item) for item in data.get("data", [])]

        return resilient_call(_fetch, default=[], op="meta.get_posts")

    def get_audience_geo(self, account_id: str, token: str | None) -> list[AudienceCity]:
        if not token:
            return []

        def _fetch() -> list[AudienceCity]:
            # VERIFY: Meta replaced audience_city with follower_demographics.
            data = _graph_get(
                f"{account_id}/insights",
                {
                    "metric": "follower_demographics",
                    "period": "lifetime",
                    "metric_type": "total_value",
                    "breakdown": "city",
                    "access_token": token,
                },
            )
            return _parse_audience(data)

        return resilient_call(_fetch, default=[], op="meta.get_audience_geo")


def _parse_ig_media(item: dict[str, Any]) -> RawPost:
    """Map one IG media object to RawPost. IG has no FB-style reaction breakdown,
    so reactions stay empty and sentiment leans on comments + engagement."""
    ts = item.get("timestamp")
    created = datetime.fromisoformat(ts.replace("Z", "+00:00")) if ts else now_ist()
    comments_node = item.get("comments", {}).get("data", [])
    comments = []
    for c in comments_node:
        cts = c.get("timestamp")
        comments.append(
            RawComment(
                platform_id=str(c.get("id")),
                text=c.get("text", ""),
                language="und",  # language detection happens in WP8 (Google NL)
                likes=int(c.get("like_count", 0)),
                created_at=(datetime.fromisoformat(cts.replace("Z", "+00:00")) if cts else created),
            )
        )
    return RawPost(
        platform_id=str(item.get("id")),
        platform="ig",
        reach=0,  # extend with per-media insights call (reach/impressions) later
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
    """Best-effort parse of the follower_demographics city breakdown."""
    out: list[AudienceCity] = []
    try:
        values = data["data"][0]["total_value"]["breakdowns"][0]["results"]
        total = sum(int(r["value"]) for r in values) or 1
        for r in values:
            city = r["dimension_values"][0]
            out.append(
                AudienceCity(
                    city=city,
                    follower_pct=round(int(r["value"]) / total * 100, 1),
                    age_band="all",
                    gender="all",
                )
            )
    except (KeyError, IndexError, TypeError):
        log.warning("audience_parse_unexpected_shape")  # VERIFY shape vs current docs
    return out


def get_meta_client(settings: Settings | None = None) -> MetaClient:
    """Factory: Fake in demo/test mode; otherwise the Facebook-Page client or the
    Instagram-Login client depending on META_SOURCE."""
    settings = settings or get_settings()
    if settings.use_fake_clients:
        return FakeMetaClient()
    if settings.meta_source == "instagram_login":
        # Local import avoids a circular import (instagram_login imports our dataclasses).
        from app.clients.instagram_login import InstagramLoginClient

        return InstagramLoginClient(settings)
    return RealMetaClient(settings)
