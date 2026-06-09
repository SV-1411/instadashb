"""Celery application + beat schedule.

All external fetching and aggregation runs here, never in the API process
(architecture rule 1). On Windows use ``--pool=solo`` (see README).
"""

from __future__ import annotations

from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "civicpulse",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone=settings.timezone,  # IST
    enable_utc=False,
    task_acks_late=True,
    worker_max_tasks_per_child=200,
)

# Beat schedule: real ingestion cycle every INGESTION_INTERVAL_MINUTES. Each run
# ingests all politicians, rebuilds aggregates, and runs spike detection.
celery_app.conf.beat_schedule = {
    "ingest-all-every-interval": {
        "task": "app.workers.tasks.ingest_all",
        "schedule": float(settings.ingestion_interval_minutes * 60),
    },
}
