# CivicPulse — Project Constitution

## What we are building
CivicPulse is a social media intelligence dashboard for Indian politicians. It aggregates
public sentiment, tracks constituency trends, detects crises, and surfaces a daily AI brief —
across Instagram, Facebook, and X. The politician connects their own accounts via OAuth;
a background worker pulls data on a schedule and the dashboard reads only from our own database.

## Non-negotiable architecture rules
1. The dashboard NEVER calls Meta / X / any external API on page load. It reads ONLY pre-computed
   aggregates from our Postgres + Redis. A background Celery worker does all external fetching.
2. All mentions from all platforms land in ONE unified `mentions` table with the same shape.
3. External API failure must NEVER crash an ingestion cycle. Wrap every external call in
   retry + backoff + graceful degradation.
4. Meta tokens expire and get revoked. Build token-health monitoring from day one. A stale
   dashboard with no warning is worse than an honestly-down one.
5. Secrets (Meta tokens, API keys) are encrypted at rest and NEVER logged.

## Tech stack (do not deviate without asking)
- Backend: FastAPI (Python 3.11+), SQLAlchemy 2.0, Pydantic v2
- Workers: Celery + Celery beat, Redis broker
- DB: PostgreSQL 15+
- Frontend: React 18 + Vite, TailwindCSS, Recharts for charts, D3 for the India map
- Push: Firebase Cloud Messaging
- NLP: Google Natural Language API + LLM batch (topic extraction)
- DM automation: ManyChat webhooks
- Local dev: run natively (see "Local run model" below). docker-compose is kept as an
  optional deployment artifact only — it is NOT the day-to-day local path on this machine.

## Local run model (this machine — native, no Docker)
Docker is intentionally avoided locally to keep the machine light. Instead we run a
self-contained native stack under `tools/` (gitignored):
- A dedicated PostgreSQL cluster created with `initdb` (trust auth, port 5433) — does NOT
  touch the system PostgreSQL service and needs no password.
- A portable Redis server on port 6379.
- `uvicorn` (api), `celery worker`, and `celery beat` run as native processes.
`infra/scripts/start-dev.ps1` provisions and starts all of it. See README.

## Code quality bar (production-ready means ALL of these)
- Every module has type hints. Pydantic models for all API request/response shapes.
- Every external integration has a mockable client (so tests don't hit live APIs).
- Test coverage: ingestion, NLP, aggregation, and spike detection MUST have unit tests.
- The spike-detection synthetic test MUST pass in CI (insert burst of negative mentions →
  assert a notification fires within one cycle). This is the single most important test.
- No hardcoded secrets. Everything via environment variables, documented in `.env.example`.
- Ruff (lint) + Black (format) + mypy (types) pass clean before any phase is "done".
- README explains how to run locally from a fresh clone in under 10 minutes.

## Database schema (the 5 core tables — already designed, build exactly this)
- politicians (id, name, constituency, state, ig_account_id, fb_page_id, meta_token[encrypted], x_handle, created_at)
- mentions (id, politician_id, platform[ig/fb/x], source_type[comment/post/mention/dm_meta], raw_text,
  language, sentiment_score[-1..1], sentiment_label, topics[], inferred_city, inferred_area,
  likes_count, platform_ts, ingested_at, processed)
- post_metrics (id, politician_id, platform, post_id, reach, impressions, likes, comments_count,
  shares, saves, react_like, react_love, react_angry, react_sad, react_haha, react_wow, captured_at)
- audience_geo (id, politician_id, snapshot_date, city, follower_pct, age_band, gender)
- aggregates (id, politician_id, bucket_hour, sentiment_score[0-100], positive_count, negative_count,
  neutral_count, top_topics[jsonb], is_spike)

## Sentiment score formula
score(0-100) = 40% reaction-ratio + 40% comment-NLP + 20% engagement-vs-30day-baseline.
Calibrate against THIS politician's own 30-day rolling average, not a global benchmark.

## Spike detection rule
spike = current_hour_negative_mentions > (7_day_hourly_avg_negative * 2.5).
On trip: fire exactly ONE Firebase push per spike event (dedupe — never spam repeats).

## What is intentionally NOT possible (don't try to build these)
- WhatsApp monitoring (no API exists — provide a manual ground-input form instead)
- Reading DM content (Meta blocks it — we only get DM metadata via ManyChat)
- Ward/pincode-level follower geo (Meta gives city-level only)
- Free real-time X data (use SocialData.tools / Apify, paid)

## Timezone
IST (Asia/Kolkata) end-to-end for all hourly bucketing and daily snapshots.

## Working agreement
- Plan first for any new phase; show the plan; wait for approval.
- After each work package, run the full verification loop and FIX what fails before
  reporting the package done. Never report "done" with failing checks.
- On finishing a package, report: what was built, what's tested, what's NOT covered,
  and the exact command to verify it.
- If a requirement is ambiguous, STOP and ask. Do not invent external API behaviour.
