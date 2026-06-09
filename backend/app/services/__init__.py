"""Business logic: ingestion, sentiment, aggregation, spike detection.
These run inside the Celery worker; the API only reads their output."""
