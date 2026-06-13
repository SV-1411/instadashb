"""FastAPI application entrypoint.

Run locally:  uvicorn app.main:app --reload --port 8000
The dashboard talks ONLY to this API; this API reads ONLY from Postgres/Redis.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.auth_meta import router as auth_meta_router
from app.api.content import router as content_router
from app.api.dashboard import router as dashboard_router
from app.api.health import router as health_router
from app.api.internal import router as internal_router
from app.api.webhooks_manychat import router as manychat_router
from app.config import get_settings
from app.core.logging import configure_logging

settings = get_settings()
configure_logging(settings.log_level)

app = FastAPI(
    title=settings.app_name,
    version=__version__,
    summary="Social media intelligence dashboard for Indian politicians.",
)

# Allowed frontend origins: localhost (dev) plus any set via CORS_ALLOW_ORIGINS
# (comma-separated) — e.g. the deployed Vercel URL in production.
_allowed_origins = ["http://localhost:5173", "http://127.0.0.1:5173"] + [
    o.strip() for o in settings.cors_allow_origins.split(",") if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(dashboard_router)
app.include_router(content_router)
app.include_router(auth_meta_router)
app.include_router(manychat_router)
app.include_router(internal_router)


@app.get("/", tags=["root"])
def root() -> dict[str, str]:
    """Tiny landing payload so the root path is not a 404."""
    return {"service": settings.app_name, "version": __version__, "docs": "/docs"}
