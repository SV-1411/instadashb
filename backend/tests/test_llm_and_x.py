"""WP9 LLM client + X (SocialData) ingestion tests."""

from __future__ import annotations

import httpx
import respx
from app.clients.llm import FakeLlmClient, OpenRouterLlmClient
from app.clients.socialdata import FakeSocialDataClient
from app.config import Settings
from app.models.mention import Mention
from app.models.politician import Politician
from app.services.x_ingest import ingest_x
from sqlalchemy import func, select
from sqlalchemy.orm import Session


def test_fake_llm_topics_and_brief() -> None:
    topics = FakeLlmClient().complete("Extract topics", "road and water issues")
    assert "roads" in topics and "water" in topics
    brief = FakeLlmClient().complete("Write a brief", "{}")
    assert len(brief) > 10


def test_openrouter_no_key_returns_empty() -> None:
    assert OpenRouterLlmClient(Settings(openrouter_api_key="")).complete("s", "u") == ""


@respx.mock
def test_openrouter_parses_completion() -> None:
    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={"choices": [{"message": {"content": "hi there"}}]})
    )
    out = OpenRouterLlmClient(Settings(openrouter_api_key="k")).complete("s", "u")
    assert out == "hi there"


def test_x_ingest_writes_and_dedupes(db_session: Session) -> None:
    pol = Politician(name="X Demo")
    db_session.add(pol)
    db_session.commit()
    db_session.refresh(pol)

    client = FakeSocialDataClient()
    first = ingest_x(db_session, client, pol.id, ["@demo"])
    second = ingest_x(db_session, client, pol.id, ["@demo"])

    assert first == 4
    assert second == 0
    total = db_session.execute(
        select(func.count(Mention.id)).where(
            Mention.politician_id == pol.id, Mention.platform == "x"
        )
    ).scalar_one()
    assert total == 4
