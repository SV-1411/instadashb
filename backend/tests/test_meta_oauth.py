"""Live Meta client + OAuth helper tests with mocked HTTP (no real network).

Proves the token exchange, account discovery, media parsing, and token-health
mapping work without ever calling the real Graph API.
"""

from __future__ import annotations

import httpx
import pytest
import respx
from app.clients import meta as meta_mod
from app.clients.meta import RealMetaClient
from app.config import Settings
from app.core.timezone import now_ist

GRAPH = "https://graph.facebook.com/v19.0"


@pytest.fixture(autouse=True)
def _fake_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    s = Settings(
        meta_app_id="appid",
        meta_app_secret="appsecret",
        meta_graph_api_version="v19.0",
        meta_oauth_redirect_uri="http://localhost:8000/api/auth/meta/callback",
    )
    monkeypatch.setattr(meta_mod, "get_settings", lambda: s)
    return s


def test_build_oauth_url_has_required_params() -> None:
    url = meta_mod.build_oauth_url("state123")
    assert "client_id=appid" in url
    assert "state=state123" in url
    assert "response_type=code" in url


@respx.mock
def test_token_exchange_and_discovery() -> None:
    respx.get(f"{GRAPH}/oauth/access_token").mock(
        return_value=httpx.Response(200, json={"access_token": "TOKEN"})
    )
    respx.get(f"{GRAPH}/me/accounts").mock(
        return_value=httpx.Response(
            200,
            json={"data": [{"id": "page1", "instagram_business_account": {"id": "ig123"}}]},
        )
    )

    short = meta_mod.exchange_code_for_token("the-code")
    long_lived = meta_mod.exchange_for_long_lived(short)
    acct = meta_mod.discover_ig_account(long_lived)

    assert short == "TOKEN"
    assert long_lived == "TOKEN"
    assert acct == {"page_id": "page1", "ig_user_id": "ig123"}


@respx.mock
def test_real_client_token_health_states() -> None:
    client = RealMetaClient(_settings())
    assert client.token_health(None).status == "missing"

    # Sequential responses on the same /me route: first OK, then a 190 error.
    respx.get(f"{GRAPH}/me").mock(
        side_effect=[
            httpx.Response(200, json={"id": "ig123"}),
            httpx.Response(400, json={"error": {"code": 190, "message": "expired"}}),
        ]
    )
    assert client.token_health("good").status == "connected"
    assert client.token_health("bad").status == "expired"


@respx.mock
def test_real_client_parses_media_and_comments() -> None:
    ts = now_ist().isoformat()
    respx.get(f"{GRAPH}/ig123/media").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "m1",
                        "timestamp": ts,
                        "like_count": 42,
                        "comments_count": 1,
                        "comments": {"data": [{"id": "c1", "text": "great work", "like_count": 3}]},
                    }
                ]
            },
        )
    )
    posts = RealMetaClient(_settings()).get_posts("ig123", "TOKEN", now_ist())
    assert len(posts) == 1
    assert posts[0].likes == 42
    assert posts[0].comments[0].text == "great work"


def _settings() -> Settings:
    return Settings(meta_app_id="appid", meta_app_secret="x", meta_graph_api_version="v19.0")
