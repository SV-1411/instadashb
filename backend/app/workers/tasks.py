"""Celery tasks — ALL external fetching + heavy computation lives here, never in
the API (architecture rule 1). Each task is wrapped so one failure never aborts
the beat loop (rule 3)."""

from __future__ import annotations

from sqlalchemy import select

from app.cache import cache_set
from app.clients.fcm import get_fcm_client
from app.clients.google_nl import get_google_nl_client
from app.clients.llm import get_llm_client
from app.clients.meta import get_meta_client
from app.clients.scraper import get_scraper_client
from app.clients.socialdata import get_socialdata_client
from app.config import get_settings
from app.core.logging import get_logger
from app.core.timezone import floor_to_hour_ist, now_ist
from app.database import SessionLocal
from app.models.mention import Mention
from app.models.politician import Politician
from app.services.aggregate import rebuild_recent_aggregates
from app.services.ai_brief import generate_daily_brief
from app.services.audience import snapshot_audience_geo
from app.services.geo_infer import assign_geo_recent
from app.services.ingest import ingest_politician
from app.services.nlp import process_nlp_batch
from app.services.scrape_ingest import ingest_scraped
from app.services.spike import detect_spike
from app.services.topics import assign_topics_recent
from app.services.x_ingest import ingest_x
from app.workers.celery_app import celery_app

log = get_logger("worker.tasks")

DEMO_POLITICIAN_ID = 1


@celery_app.task(name="app.workers.tasks.heartbeat_insert_mock_mention")
def heartbeat_insert_mock_mention() -> int:
    """WP1 liveness heartbeat (kept for the WP1 exit test). Real work is below."""
    db = SessionLocal()
    try:
        mention = Mention(
            politician_id=DEMO_POLITICIAN_ID,
            platform="ig",
            source_type="comment",
            raw_text="[heartbeat] mock mention",
            language="en",
            sentiment_score=0.0,
            sentiment_label="neutral",
            topics=[],
            likes_count=0,
            platform_ts=now_ist(),
            processed=False,
        )
        db.add(mention)
        db.commit()
        db.refresh(mention)
        return mention.id
    except Exception:  # noqa: BLE001
        db.rollback()
        log.exception("heartbeat_mock_mention_failed")
        return -1
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.ingest_all")
def ingest_all() -> int:
    """Ingest every politician, then refresh aggregates + spike status. One bad
    politician is logged and skipped — the cycle continues."""
    db = SessionLocal()
    processed = 0
    try:
        meta = get_meta_client()
        fcm = get_fcm_client()
        scraper = get_scraper_client()
        nl = get_google_nl_client()
        socialdata = get_socialdata_client()
        llm = get_llm_client()
        settings = get_settings()
        scrape_q = [q.strip() for q in settings.scraper_queries.split(",") if q.strip()]
        x_q = [q.strip() for q in settings.x_queries.split(",") if q.strip()]
        politicians = db.execute(select(Politician)).scalars().all()
        for pol in politicians:
            try:
                ingest_politician(db, meta, pol)
                if scrape_q:
                    ingest_scraped(db, scraper, pol.id, scrape_q)
                if x_q:
                    ingest_x(db, socialdata, pol.id, x_q)
                # Refine sentiment with Google NL (sampled), then tag topics + geo, BEFORE rollup.
                process_nlp_batch(db, nl, politician_id=pol.id, settings=settings)
                assign_topics_recent(db, pol.id, llm=llm)
                assign_geo_recent(db, pol.id)
                snapshot_audience_geo(db, meta, pol)
                rebuild_recent_aggregates(db, pol.id, hours=48)
                detect_spike(db, fcm, pol.id, floor_to_hour_ist(now_ist()))
                generate_daily_brief(db, llm, pol.id, force=True)
                # Maintain token-health cache for the read path (no network on read).
                health = meta.token_health(pol.meta_token)
                cache_set(
                    f"token_health:{pol.id}",
                    {"status": health.status, "detail": health.detail},
                    ttl=3600,
                )
                # Invalidate the command-center cache so the dashboard sees fresh data.
                cache_set(f"cc:{pol.id}", None, ttl=1)
                processed += 1
            except Exception:  # noqa: BLE001 - never let one tenant kill the cycle
                db.rollback()
                log.exception("ingest_politician_failed", politician_id=pol.id)
        log.info("ingest_all_done", processed=processed)
        return processed
    except Exception:  # noqa: BLE001
        log.exception("ingest_all_failed")
        return processed
    finally:
        db.close()
