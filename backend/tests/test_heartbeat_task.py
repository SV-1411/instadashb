"""WP1 exit-test core: the beat heartbeat task inserts a mock mention via the
worker → Postgres path. We call the task body directly (no broker needed) with
SessionLocal pointed at the test DB."""

from __future__ import annotations

import pytest
from app.models.mention import Mention
from app.workers import tasks
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker


def test_heartbeat_inserts_mock_mention(db_engine: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    factory = sessionmaker(bind=db_engine, expire_on_commit=False, future=True)
    monkeypatch.setattr(tasks, "SessionLocal", factory)

    mention_id = tasks.heartbeat_insert_mock_mention()
    assert mention_id > 0

    with factory() as session:
        row = session.get(Mention, mention_id)
        assert row is not None
        assert row.source_type == "comment"
        assert row.platform == "ig"
        assert row.processed is False


def test_heartbeat_never_raises_on_db_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Rule 3: a failed cycle must degrade gracefully, never raise."""

    class _BoomSession:
        def __call__(self) -> _BoomSession:
            return self

        def add(self, *_: object) -> None:
            raise RuntimeError("db is down")

        def rollback(self) -> None:
            pass

        def close(self) -> None:
            pass

    monkeypatch.setattr(tasks, "SessionLocal", _BoomSession())
    assert tasks.heartbeat_insert_mock_mention() == -1
