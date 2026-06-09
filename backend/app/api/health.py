"""Health endpoint.

Checks DB and Redis connectivity. This is the ONLY place the API touches Redis/DB
for liveness — it does NOT call any external (Meta/X) API (architecture rule 1).
Returns 200 with status "ok" when healthy, "degraded" otherwise (still 200 so the
dashboard can show an honest banner rather than crash — rule 4).
"""

from __future__ import annotations

import redis
from fastapi import APIRouter
from sqlalchemy import text

from app import __version__
from app.config import get_settings
from app.database import engine
from app.schemas.health import DependencyHealth, HealthResponse

router = APIRouter(tags=["health"])


def _check_db() -> DependencyHealth:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return DependencyHealth(name="postgres", ok=True)
    except Exception as exc:  # noqa: BLE001 - report, never crash
        return DependencyHealth(name="postgres", ok=False, detail=type(exc).__name__)


def _check_redis() -> DependencyHealth:
    try:
        client = redis.Redis.from_url(get_settings().redis_url, socket_connect_timeout=2)
        client.ping()
        return DependencyHealth(name="redis", ok=True)
    except Exception as exc:  # noqa: BLE001 - report, never crash
        return DependencyHealth(name="redis", ok=False, detail=type(exc).__name__)


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Liveness/readiness probe used by every service and the dev orchestrator."""
    deps = [_check_db(), _check_redis()]
    status = "ok" if all(d.ok for d in deps) else "degraded"
    return HealthResponse(
        status=status,
        service=get_settings().app_name,
        version=__version__,
        dependencies=deps,
    )
