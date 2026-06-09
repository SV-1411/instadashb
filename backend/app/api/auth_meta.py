"""Meta OAuth connect flow (one-time account linking).

GET /api/auth/meta/connect  -> redirects the owner to Meta's consent screen.
GET /api/auth/meta/callback -> exchanges the code for a long-lived token, discovers
the IG Business account, and stores the token ENCRYPTED on the politician row.

CSRF state is stored in Redis with a short TTL and is single-use.
"""

from __future__ import annotations

import secrets

import redis
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clients.meta import (
    _graph_get,
    build_oauth_url,
    discover_ig_account,
    exchange_code_for_token,
    exchange_for_long_lived,
)
from app.clients.resilient import ExternalServiceError
from app.config import get_settings
from app.core.logging import get_logger
from app.database import get_db
from app.models.politician import Politician

log = get_logger("api.auth_meta")
router = APIRouter(prefix="/api/auth/meta", tags=["auth"])

_STATE_PREFIX = "oauth_state:"
_STATE_TTL = 600


def _redis() -> redis.Redis:
    return redis.Redis.from_url(get_settings().redis_url, decode_responses=True)


@router.get("/connect")
def connect() -> RedirectResponse:
    """Begin OAuth: stash a single-use state and redirect to Meta."""
    s = get_settings()
    if not s.meta_app_id or s.use_fake_clients:
        raise HTTPException(
            status_code=400,
            detail="Meta is not configured. Set META_APP_ID/SECRET and USE_FAKE_CLIENTS=false.",
        )
    state = secrets.token_urlsafe(24)
    _redis().set(f"{_STATE_PREFIX}{state}", "1", ex=_STATE_TTL)
    return RedirectResponse(url=build_oauth_url(state))


@router.get("/callback")
def callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Finish OAuth: validate state, exchange code, store the encrypted token."""
    key = f"{_STATE_PREFIX}{state}"
    if not _redis().delete(key):  # single-use; 0 deleted => invalid/expired
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state.")

    try:
        short = exchange_code_for_token(code)
        long_lived = exchange_for_long_lived(short)
        acct = discover_ig_account(long_lived)
        profile = _graph_get(
            acct["ig_user_id"], {"fields": "username,name", "access_token": long_lived}
        )
    except ExternalServiceError as exc:
        log.warning("meta_oauth_failed", error=str(exc))
        raise HTTPException(status_code=502, detail="Meta OAuth exchange failed.") from exc

    ig_user_id = acct["ig_user_id"]
    name = profile.get("name") or profile.get("username") or "Connected Account"

    pol = db.execute(
        select(Politician).where(Politician.ig_account_id == ig_user_id)
    ).scalar_one_or_none()
    if pol is None:
        pol = Politician(name=name, ig_account_id=ig_user_id)
        db.add(pol)
    pol.fb_page_id = acct["page_id"]
    pol.meta_token = long_lived  # encrypted at rest by EncryptedString
    db.commit()
    db.refresh(pol)
    log.info("meta_connected", politician_id=pol.id, ig_user_id=ig_user_id)

    # Bounce back to the dashboard.
    front = get_settings().meta_oauth_redirect_uri.split("/api/")[0].replace(":8000", ":5173")
    return RedirectResponse(url=f"{front}/?connected={pol.id}")
