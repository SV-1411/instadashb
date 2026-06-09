"""Shared test fixtures.

A throwaway FERNET_KEY is generated before app modules import, so encryption
tests never depend on a real secret. DB tests run against a *separate*
``civicpulse_test`` database and are skipped (not failed) if Postgres is
unreachable, so the suite is green in any environment while still exercising
the real DB when one is available.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

from cryptography.fernet import Fernet

# Must be set BEFORE any `app.*` import so Settings/security pick it up.
os.environ.setdefault("FERNET_KEY", Fernet.generate_key().decode())
os.environ.setdefault("APP_ENV", "test")

import app.models  # noqa: E402,F401  (registers all tables on Base.metadata)
import pytest  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.database import Base  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.engine import Engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402


def _test_db_url() -> str:
    """Use TEST_DATABASE_URL if given, else the main URL with ``_test`` appended
    to the database name only (the final path segment)."""
    override = os.environ.get("TEST_DATABASE_URL")
    if override:
        return override
    base, _, db_name = get_settings().database_url.rpartition("/")
    return f"{base}/{db_name}_test"


@pytest.fixture(scope="session")
def db_engine() -> Iterator[Engine]:
    """Session-scoped engine bound to the test DB; skips if Postgres is down."""
    engine = create_engine(_test_db_url(), future=True)
    try:
        with engine.connect():
            pass
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Postgres test DB unreachable ({type(exc).__name__}); skipping DB tests.")
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    _flush_test_cache()
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


def _flush_test_cache() -> None:
    """Drop dashboard/token cache keys so a prior run's data can't leak in
    (the test DB resets ids each run, so cache keys like ``cc:1`` could collide)."""
    try:
        import redis as _redis

        client = _redis.Redis.from_url(
            get_settings().redis_url, socket_connect_timeout=1, decode_responses=True
        )
        for pattern in ("cc:*", "token_health:*", "brief:*"):
            keys = list(client.scan_iter(pattern))
            if keys:
                client.delete(*keys)
    except Exception:  # noqa: BLE001 - cache flush is best-effort
        pass


@pytest.fixture
def db_session(db_engine: Engine) -> Iterator[Session]:
    """Function-scoped session; truncates all tables on teardown."""
    factory = sessionmaker(bind=db_engine, expire_on_commit=False, future=True)
    session = factory()
    try:
        yield session
    finally:
        session.rollback()
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()
        session.close()
