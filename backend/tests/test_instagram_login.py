"""Instagram-Login client tests (graph.instagram.com) with mocked HTTP."""

from __future__ import annotations

import httpx
import respx
from app.clients.instagram_login import InstagramLoginClient
from app.config import Settings
from app.core.timezone import now_ist

IG = "https://graph.instagram.com"


def _client() -> InstagramLoginClient:
    return InstagramLoginClient(Settings())


def test_token_health_missing() -> None:
    assert _client().token_health(None).status == "missing"


@respx.mock
def test_token_health_connected_and_expired() -> None:
    respx.get(f"{IG}/me").mock(
        side_effect=[
            httpx.Response(200, json={"user_id": "123", "username": "demo"}),
            httpx.Response(400, json={"error": {"message": "OAuthException"}}),
        ]
    )
    assert _client().token_health("good").status == "connected"
    assert _client().token_health("bad").status == "expired"


@respx.mock
def test_get_posts_parses_media_and_comments() -> None:
    respx.get(f"{IG}/me/media").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "m1",
                        "timestamp": now_ist().isoformat(),
                        "like_count": 10,
                        "comments_count": 1,
                        "comments": {"data": [{"id": "c1", "text": "nice work", "like_count": 2}]},
                    }
                ]
            },
        )
    )
    posts = _client().get_posts("me", "token", now_ist())
    assert len(posts) == 1
    assert posts[0].likes == 10
    assert posts[0].platform == "ig"
    assert posts[0].comments[0].text == "nice work"
