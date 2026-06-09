"""Health-check response shape."""

from __future__ import annotations

from pydantic import BaseModel


class DependencyHealth(BaseModel):
    """Status of a single backing dependency."""

    name: str
    ok: bool
    detail: str | None = None


class HealthResponse(BaseModel):
    """Overall service health (used by /health and the dev orchestrator)."""

    status: str  # "ok" | "degraded"
    service: str
    version: str
    dependencies: list[DependencyHealth] = []
