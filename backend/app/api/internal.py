"""Internal ops endpoint: cron-triggered ingestion.

In the free, worker-less deployment there is no Celery beat. An external scheduler
(GitHub Actions / cron-job.org) POSTs here every ``INGESTION_INTERVAL_MINUTES`` with the
shared ``X-Cron-Secret`` header. We run the exact same ``ingest_all()`` pipeline
synchronously — it writes aggregates to Postgres and the AI brief to Redis just as the
Celery worker would. This keeps architecture rule 1 intact (the read API still never
touches an external service) while removing the always-on worker that free tiers can't run.
"""

from __future__ import annotations

import hmac

from fastapi import APIRouter, Header, HTTPException

from app.config import get_settings
from app.core.logging import get_logger
from app.workers.tasks import ingest_all

router = APIRouter(prefix="/api/internal", tags=["internal"])
log = get_logger("api.internal")


@router.post("/run-ingestion")
def run_ingestion(x_cron_secret: str | None = Header(default=None)) -> dict[str, str | int]:
    """Run one full ingestion cycle. Protected by the ``X-Cron-Secret`` shared secret.

    Returns the number of politicians processed. One bad tenant never aborts the cycle
    (see ``ingest_all``), so a 200 with ``processed`` is the normal success signal.
    """
    expected = get_settings().cron_secret.get_secret_value()
    if not expected:
        raise HTTPException(
            status_code=503, detail="Ingestion endpoint disabled (no CRON_SECRET set)."
        )
    if not x_cron_secret or not hmac.compare_digest(x_cron_secret, expected):
        raise HTTPException(status_code=401, detail="Invalid or missing X-Cron-Secret.")
    processed = ingest_all()
    log.info("cron_ingestion_done", processed=processed)
    return {"status": "ok", "processed": processed}
