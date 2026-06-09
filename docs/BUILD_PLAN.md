# CivicPulse — Complete Build Plan (WP1–WP11)

This is the master plan referenced by `CLAUDE.md`. Each work package lists: files,
key functions/classes, external services + mock strategy, exit test, and failure defenses.
Build order is top-to-bottom; the dependency graph at the end shows what can parallelize.

Monorepo layout convention:

```
POLITICIANDASHBOARD/
  CLAUDE.md                 # project constitution
  .env.example              # every env var documented
  docs/                     # BUILD_PLAN.md, ARCHITECTURE.md (later), runbooks
  backend/
    app/
      config.py             # Settings (env only)
      database.py           # SQLAlchemy 2.0 engine/session/Base
      main.py               # FastAPI app
      core/                 # security (Fernet), timezone (IST), logging
      models/               # 5 ORM tables
      schemas/              # Pydantic v2 request/response
      api/                  # routers (read-only: DB/Redis only)
      clients/              # external clients, each behind an interface + Fake (WP2+)
      services/             # sentiment, aggregation, spike, nlp, topics (WP3+)
      workers/              # celery_app + tasks (all external I/O lives here)
    alembic/                # migrations
    tests/
  frontend/                 # React 18 + Vite + Tailwind + Recharts + D3
  infra/                    # start-dev.ps1 (native), docker-compose.yml (optional)
  tools/                    # gitignored: local pg cluster + portable redis
```

Reusable patterns (defined in WP1/WP2, reused everywhere):
- **Mockable client** = an abstract interface in `app/clients/<svc>.py` with a real impl
  and a `Fake<Svc>Client` used by tests. No test ever hits a live API.
- **Resilient call** = `tenacity` retry + exponential backoff wrapping every external call,
  returning a graceful-degradation value on final failure (rule 3).
- **Read path** = API routers read ONLY Postgres/Redis; Redis caches the latest aggregates.

---

## Phase 1 — MVP (free APIs only)

### WP1 — Foundation  ✅ (this package)
**Files:** monorepo skeleton, `docker-compose.yml` (optional), `start-dev.ps1`, all 5 models,
`config.py`, `database.py`, `core/{security,timezone,logging}.py`, `main.py`, `api/health.py`,
`workers/{celery_app,tasks}.py`, Alembic, React shell (6 routes), tests.
**Key functions/classes:** `Settings`, `EncryptedString`, `now_ist/floor_to_hour_ist`,
`health()`, `heartbeat_insert_mock_mention()`.
**External services:** none. **Mock strategy:** n/a.
**Exit test:** `alembic upgrade head` runs clean; `pytest` green; `/health` → 200;
beat heartbeat inserts a mock mention (unit test `test_heartbeat_task.py`); `npm run build` clean.
**What can go wrong / defense:** Windows Celery prefork bug → use `--pool=solo`; unknown system
PG password → isolated `initdb` cluster on port 5433; secret leakage → `EncryptedString` +
log scrubber.

### WP2 — Meta OAuth + ingestion
**Files:** `app/clients/meta.py` (`MetaClient` interface + `RealMetaClient` + `FakeMetaClient`),
`app/api/auth_meta.py` (OAuth connect + callback), `app/services/ingest.py`,
`app/workers/tasks.py` (`ingest_politician`, beat every 30 min), `schemas/meta.py`.
**Key functions/classes:** `MetaClient.get_posts/get_post_metrics/get_reactions/get_comments`,
`exchange_code_for_token`, `store_token` (writes `EncryptedString`), `token_health_check`,
`ingest_politician(politician_id)` → writes `mentions` + `post_metrics`.
**External services:** Meta Graph API (OAuth, posts, insights, reactions, comments).
**Mock strategy:** `FakeMetaClient` returns canned posts/comments fixtures; `respx` mocks HTTP.
**Exit test:** with `FakeMetaClient`, one ingestion cycle writes N mentions + M post_metrics;
token-health endpoint reports `connected/expired/revoked`; dedupe prevents duplicate rows on re-run.
**Defense:** token expiry/revoke → status flagged + reconnect banner (never crash); every call
wrapped in retry/backoff; partial-platform failure still commits what succeeded.

### WP3 — Reaction sentiment + scores + Command Center
**Files:** `app/services/sentiment_reactions.py`, `app/services/aggregate.py`,
`app/workers/tasks.py` (`build_aggregates`), `app/api/command_center.py`,
frontend `pages/CommandCenter.tsx` (gauge, trend, counts via Recharts).
**Key functions/classes:** `reaction_ratio_score(post_metrics)`,
`engagement_vs_baseline(politician_id)` (30-day rolling), `compute_hourly_aggregate(bucket)`
upserting `aggregates` (idempotent), `get_command_center(politician_id)` reads aggregates/Redis.
**External services:** none (uses stored data). **Mock strategy:** seed fixtures in DB.
**Exit test:** given seeded metrics, aggregator produces deterministic 0–100 score; re-running the
same bucket does not double-count; Command Center API returns the cached aggregate (no external call).
**Defense:** missing baseline (new account) → fall back to neutral 50 with a "calibrating" flag;
idempotent upsert via unique `(politician_id, bucket_hour)`.

### WP4 — Your Identity module
**Files:** `app/services/audience.py`, `app/workers/tasks.py` (`snapshot_audience_geo` daily),
`app/api/identity.py`, frontend `pages/YourIdentity.tsx` + `components/IndiaMap.tsx` (D3).
**Key functions/classes:** `follower_growth_series`, `rank_posts`, `demographics_snapshot`,
`snapshot_audience_geo(politician_id)` writes `audience_geo`.
**External services:** Meta insights (audience city/age/gender). **Mock:** `FakeMetaClient` geo fixtures.
**Exit test:** daily snapshot writes one `audience_geo` row-set per city; India map renders city
bubbles from API data; post ranking sorts by engagement deterministically.
**Defense:** Meta returns city-level only (documented); missing geo → map shows "no data" state.

### WP5 — Spike detection + push  ⭐ (crown-jewel test)
**Files:** `app/services/spike.py`, `app/clients/fcm.py` (`FcmClient` + `FakeFcmClient`),
`app/workers/tasks.py` (`detect_spikes`), `app/models` (spike-event dedupe table or Redis key),
`tests/test_spike_detection.py`.
**Key functions/classes:** `hourly_negative_count`, `seven_day_hourly_avg_negative`,
`is_spike = current > avg * 2.5`, `fire_spike_push(once)` with dedupe key
`spike:{politician}:{bucket_hour}`.
**External services:** FCM. **Mock:** `FakeFcmClient` records sent pushes in memory.
**Exit test (MANDATORY, CI):** seed a 7-day baseline of low negatives → insert a burst of negative
mentions in the current hour → run `detect_spikes` → assert `is_spike` set AND exactly ONE
`FakeFcmClient` push recorded; run again → assert NO second push (dedupe). Deterministic, no live APIs.
**Defense:** FCM token refresh handled; dedupe guarantees one push per spike event; baseline of zero
→ require a minimum absolute floor to avoid false spikes on tiny accounts.

### WP6 — ManyChat DMs
**Files:** `app/api/webhooks_manychat.py`, `app/clients/manychat.py` (signature verify),
`app/services/dm.py`, frontend `pages/CrisisDMs.tsx`.
**Key functions/classes:** `verify_manychat_signature`, `handle_dm_event` → stores DM *metadata*
only (`source_type="dm_meta"`, no content), `keyword_flow_router`.
**External services:** ManyChat webhooks. **Mock:** signed fixture payloads.
**Exit test:** a signed webhook with a known keyword stores a `dm_meta` mention; bad signature → 401;
Crisis & DMs screen lists DM activity counts.
**Defense:** we never store/read DM content (Meta policy); reject unsigned/forged webhooks.

### WP7 — Phase 1 integration + demo polish
**Files:** seed script `backend/scripts/seed_demo.py`, e2e smoke test, frontend polish across modules.
**Exit test:** fresh clone → `start-dev.ps1` → seed → all 6 modules render real data from aggregates;
full `pytest` + frontend build green; demo runbook works end-to-end.
**Defense:** smoke test asserts no module calls an external API on load.

---

## Phase 2 — Sentiment & trends

### WP8 — NLP pipeline (Google NL API)
**Files:** `app/clients/google_nl.py` (`+ FakeGoogleNlClient`), `app/services/nlp.py`,
`app/services/sentiment_blend.py`, `app/workers/tasks.py` (`process_mention_nlp`).
**Key functions/classes:** `detect_language`, `analyze_sentiment`, `sample_for_cost(rate)`,
`blended_score = 0.4*reaction + 0.4*nlp + 0.2*engagement_baseline`.
**External services:** Google Natural Language API. **Mock:** `FakeGoogleNlClient` deterministic scores.
**Exit test:** comments get `sentiment_score`/`label`; blended score matches the 40/40/20 formula on
fixtures; sampling caps API calls at `NLP_SAMPLE_RATE`.
**Defense:** language routing (hi/mr/en); cost sampling; NL API failure → fall back to reaction-only score.

### WP9 — Topics + X (Public Voice, Trends)
**Files:** `app/services/topics.py` (Hindi/Marathi/English dictionary + LLM batch),
`app/clients/openai_llm.py`, `app/clients/socialdata.py` (`+ Fake`),
`app/api/{public_voice,trends}.py`, frontend `pages/{PublicVoice,Trends}.tsx`.
**Key functions/classes:** `extract_topics_batch`, `TopicDictionary`, `fetch_x_mentions`
(SocialData.tools), `trend_series`.
**External services:** SocialData.tools (paid X), OpenAI (batch topics). **Mock:** Fakes + fixtures.
**Exit test:** topics populate `mentions.topics`; X mentions land in the unified `mentions` table;
Public Voice + Trends render from aggregates.
**Defense:** X is paid/rate-limited → budget guard + graceful skip; LLM batch failure → dictionary fallback.

### WP10 — Geo inference + misinformation
**Files:** `app/data/constituency_lookup.csv`, `app/services/geo_infer.py`,
`app/services/misinfo.py`, frontend choropleth component.
**Key functions/classes:** `infer_location(text, bio)`, `constituency_lookup`,
`misinformation_claim_volume` flag.
**External services:** none new. **Exit test:** location inference tags `inferred_city/area`;
city sentiment choropleth renders; misinformation flag trips on claim-volume threshold.
**Defense:** ward/pincode geo impossible (city-level only); inference confidence threshold to avoid noise.

---

## Phase 3 — Intelligence layer

### WP11 — AI Brief + reports + multi-tenant + admin
**Files:** `app/services/ai_brief.py`, `app/clients/openai_llm.py` (reuse), `app/services/reports.py`
(PDF/CSV), `app/api/{ai_brief,admin,ground_input}.py`, frontend `pages/AIBrief.tsx` + admin.
**Key functions/classes:** `generate_daily_brief(politician_id)` (gpt-4o-mini summary + actions),
`export_pdf/export_csv`, `ground_intelligence_form` (manual WhatsApp-gap input), tenant scoping.
**External services:** OpenAI. **Mock:** `FakeLlmClient`. **Exit test:** daily brief row generated per
tenant from aggregates; PDF/CSV export works; admin can onboard a new politician; data is tenant-isolated.
**Defense:** LLM cost cap + cache one brief/day; multi-tenant row-level scoping on every query.

---

## Dependency graph

```
WP1 ──┬─> WP2 ──┬─> WP3 ──> WP4
      │         ├─> WP5 (needs mentions from WP2; FCM independent)
      │         └─> WP6 (ManyChat; independent of WP3/4/5)
      │
      └────────────────────────> WP7 (integration; needs WP2–WP6)

Phase 2:  WP8 ──> WP9 ──> WP10        (WP8 needs WP3 scores; WP9 needs WP8 sentiment)
Phase 3:  WP11                        (needs WP3 aggregates + WP8/WP9 for rich briefs)
```

**Sequential (hard):** WP1 → WP2 → WP3; WP5 needs WP2; WP8 → WP9 → WP10; WP11 last.
**Parallelizable after WP2:** WP4, WP5, WP6 can be built concurrently (different surfaces).
**Parallelizable after WP3:** Command Center (WP3) and Your Identity (WP4) are independent UIs.

## Open decisions (need a human)
1. **Paid X source:** SocialData.tools vs Apify — pricing/quota choice (WP9).
2. **Hosting/deploy target:** VPS vs managed (Fly/Render/GCP) — affects WP-prod gate.
3. **FCM project + Google Cloud project:** who owns the Firebase/GCP project and billing (WP5/WP8).
4. **Encryption key management:** env var now; KMS/secret-manager in prod? (rule 5).
5. **OpenAI account/budget** for AI Brief + topic batch (WP9/WP11).
