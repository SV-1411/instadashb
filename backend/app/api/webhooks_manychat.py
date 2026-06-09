"""ManyChat webhook receiver (WP6).

ManyChat is configured to POST here on a keyword flow. We authenticate with a
shared secret header (configure it as a custom header in ManyChat's External
Request) and store DM metadata only.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.logging import get_logger
from app.database import get_db
from app.models.politician import Politician
from app.services.dm import handle_dm_event

log = get_logger("api.webhooks_manychat")
router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


class ManyChatEvent(BaseModel):
    """Permissive: ManyChat payloads vary; we only read a few metadata fields."""

    model_config = ConfigDict(extra="allow")

    event_id: str
    keyword: str | None = None
    politician_id: int | None = None
    platform: str = "ig"


@router.post("/manychat")
def manychat_webhook(
    event: ManyChatEvent,
    db: Session = Depends(get_db),
    x_civicpulse_secret: str | None = Header(default=None),
) -> dict[str, object]:
    """Receive a ManyChat keyword event; store DM metadata. Returns {stored: bool}."""
    secret = get_settings().manychat_webhook_secret.get_secret_value()
    if secret and x_civicpulse_secret != secret:
        raise HTTPException(status_code=401, detail="Bad or missing webhook secret.")

    politician_id = event.politician_id
    if politician_id is None:
        # Single-tenant fallback: attach to the first (only) politician.
        politician_id = db.execute(
            select(Politician.id).order_by(Politician.id).limit(1)
        ).scalar_one_or_none()
    if politician_id is None:
        raise HTTPException(status_code=404, detail="No politician to attach the DM to.")

    stored = handle_dm_event(db, politician_id, event.event_id, event.keyword, event.platform)
    return {"stored": stored, "politician_id": politician_id}
