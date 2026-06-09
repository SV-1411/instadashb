# CivicPulse — Full Project Context & Knowledge Handoff

This document captures everything needed to understand, run, extend, and deploy
CivicPulse — the architecture, every component, the decisions and their reasons,
the build journey, known gotchas, and what's done vs pending. If you're a new
developer (or a future AI session), read this first.

Repo: https://github.com/SV-1411/instadashb · Local: `D:\POLITICIANDASHBOARD`

---

## 1. What CivicPulse is
A social-media intelligence dashboard for Indian politicians. It aggregates public
sentiment, tracks constituency trends, detects crises (negative spikes), and surfaces
a daily AI brief — across Instagram, Facebook, and X. The politician connects their own
account; a background worker pulls data on a schedule; the dashboard reads only from our DB.

**The single most important architecture rule:** the dashboard NEVER calls Meta/X/any
external API on page load. A Celery worker does ALL external fetching and writes
pre-computed aggregates to Postgres + Redis. The API/dashboard reads only those.

Full product spec is in `CLAUDE.md` (the project constitution). The 11-work-package plan
is in `docs/BUILD_PLAN.md`.

## 2. Tech stack
- **Backend:** FastAPI (Python 3.11), SQLAlchemy 2.0, Pydantic v2, Alembic.
- **Workers:** Celery + Celery beat, Redis broker.
- **DB:** PostgreSQL. **Cache/broker:** Redis.
- **Frontend:** React 18 + Vite + TypeScript, TailwindCSS (glassmorphism), Recharts, a custom SVG India map.
- **External:** Meta Graph API (Facebook-Page path) + Instagram Login API (no-Page path),
  Google Natural Language API, OpenRouter (LLM, free models), SocialData.tools (X), a scraper
  (Apify/SociaVault), Firebase Cloud Messaging, ManyChat webhooks.

## 3. Local dev model — NATIVE, no Docker (important)
Docker was intentionally avoided locally (deemed heavy on the dev machine). Instead a
self-contained native stack lives under `tools/` (gitignored):
- A dedicated **Postgres cluster** created with `initdb` on **port 5433** (trust auth, role/db
  `civicpulse`, plus `civicpulse_test`). Does NOT touch any system Postgres. No password needed.
- A **portable Redis** on 6379.
- `uvicorn` (api), `celery worker`, `celery beat` run as native processes.
- Provisioned/started by `infra/scripts/start-dev.ps1` (`-Stop` to stop pg+redis).
- `docker-compose.yml` exists in `infra/` but is for CI/deploy only, NOT local.
- **Windows gotcha:** Celery must run with `--pool=solo` (prefork is broken on Windows).

Full run/test steps: `docs/TESTING.md`. Deploy: `docs/DEPLOY.md`.

## 4. Repository layout
```
POLITICIANDASHBOARD/
  CLAUDE.md                  # constitution (product spec + rules)
  docs/                      # BUILD_PLAN, TESTING, DEPLOY, CONNECT_INSTAGRAM, FLAWS_AND_FIXES, this file
  .env.example               # every env var documented
  infra/                     # start-dev.ps1 (native), docker-compose.yml (deploy)
  tools/                     # gitignored: local pg cluster + portable redis
  backend/
    pyproject.toml           # deps + ruff/black/mypy/pytest config
    alembic/                 # migrations (2 so far)
    app/
      config.py              # Settings (env-only; SecretStr for secrets)
      database.py            # SQLAlchemy 2.0 engine/session/Base
      cache.py               # Redis JSON cache (degrades to miss if down)
      main.py                # FastAPI app + routers
      core/                  # security (Fernet EncryptedString), timezone (IST), logging (scrubs secrets)
      models/                # the 5 ORM tables
      schemas/               # Pydantic v2 request/response
      api/                   # routers: health, dashboard, content, auth_meta, webhooks_manychat
      clients/               # external clients (interface + Real + Fake + factory each)
      services/              # ingest, nlp, topics, geo_infer, misinfo, aggregate, spike, ai_brief, dm, audience, x_ingest, scrape_ingest
      workers/               # celery_app (+ beat schedule) + tasks (ingest_all)
      scripts/               # seed_demo, connect_with_token, connect_ig_login, diagnose_meta, diagnose_ig
    tests/                   # 62 tests
  frontend/
    src/
      App.tsx                # shell: sidebar + topbar (glass), PoliticianProvider
      router.tsx             # routes for all modules
      index.css              # glass theme (.glass/.glass-card, warm gradient bg)
      tailwind.config.js     # cream/beige/brown palette
      layout/Sidebar.tsx
      components/IndiaMap.tsx # interactive SVG bubble map (zoom + hover)
      lib/                   # api.ts (typed client), PoliticianContext, useData hook, modules
      pages/                 # CommandCenter, YourIdentity, PublicVoice, Trends, CrisisDMs, AIBrief, GroundInput, ConnectInstagram
```

## 5. Data model (the 5 core tables — fixed by the constitution)
- **politicians** — the tenant. `meta_token` is encrypted at rest (Fernet `EncryptedString`).
- **mentions** — UNIFIED table; every platform/source lands here with the same shape.
  `platform` (ig/fb/x/ground), `source_type` (comment/post/mention/dm_meta), `raw_text`, `language`,
  `sentiment_score` (-1..1), `sentiment_label`, `topics[]`, `inferred_city/area`, `likes_count`,
  `platform_ts`, `ingested_at`, `processed`. **Dedupe:** unique `(politician_id, platform, platform_mention_id)`.
- **post_metrics** — per-post engagement + FB reaction breakdown, time-series (new row per cycle).
- **audience_geo** — daily city-level audience snapshot (Meta gives city-level only).
- **aggregates** — pre-computed per-hour rows the dashboard reads. 0-100 score, pos/neg/neutral counts,
  `top_topics` (jsonb), `is_spike`. Unique `(politician_id, bucket_hour)` → idempotent.

## 6. The pipeline (all inside the Celery worker — `app/workers/tasks.py::ingest_all`)
Per politician, each cycle:
1. **ingest_politician** — Meta client → posts/comments → `mentions` (provisional lexicon sentiment,
   `processed=False`) + `post_metrics`. Dedupes on `platform_mention_id`. Fetches the **latest 50 posts**
   (no date filter — see Gotchas).
2. **ingest_scraped** / **ingest_x** — optional supplemental mentions (if queries configured).
3. **process_nlp_batch** — Google NL refines comment sentiment (cost-sampled via `NLP_SAMPLE_RATE`,
   lexicon fallback), sets `processed=True`.
4. **assign_topics_recent** — multilingual keyword dictionary (Hindi/Marathi/English) + LLM fallback → `mentions.topics`.
5. **assign_geo_recent** — infer city from text (known-place table) → `inferred_city/area`.
6. **snapshot_audience_geo** — once/day audience snapshot.
7. **rebuild_recent_aggregates** — recompute hourly `aggregates` (idempotent upsert), incl. `top_topics`.
8. **detect_spike** — the crown jewel (below).
9. **generate_daily_brief** — LLM brief from aggregates, cached in Redis (worker writes; API only reads).

Beat schedule: `ingest_all` every `INGESTION_INTERVAL_MINUTES` (default 30).

### Sentiment score (0-100)
`0.40*reaction-ratio + 0.40*comment-NLP + 0.20*engagement-vs-30day-baseline`, calibrated against THIS
politician's own 30-day rolling average. In `app/services/aggregate.py`. The comment-NLP component is
`mentions.sentiment_score` (lexicon until WP8, Google NL after).

### Spike detection (the product's core job — `app/services/spike.py`)
`spike = current_hour_negative > max(7day_hourly_avg_negative * SPIKE_MULTIPLIER, SPIKE_MIN_ABSOLUTE)`.
On the transition from `is_spike=False -> True`, fire EXACTLY ONE FCM push and persist the flag —
this is the crash-safe dedupe (no double pushes). The synthetic test
`tests/test_spike_detection.py` is mandatory and passing.

## 7. External clients — the mockable pattern
Every external service has: an interface, a `Real*` impl (live HTTP via `httpx`, wrapped in
`resilient_call` = tenacity retry + backoff + graceful default), a `Fake*` impl (deterministic,
offline), and a `get_*_client()` factory. Tests never hit live APIs (HTTP mocked with `respx`).

Two global switches in `.env`:
- **`USE_FAKE_CLIENTS`** (default true) — true = all Fakes (offline demo). false = real clients.
- **`META_SOURCE`** = `facebook` | `instagram_login` — which Instagram path to use.

| Service | File | Notes |
|---|---|---|
| Meta (FB-Page path) | `clients/meta.py` `RealMetaClient` | `graph.facebook.com`, needs a linked Facebook Page |
| **Instagram Login (no Page)** | `clients/instagram_login.py` | `graph.instagram.com`, needs NO Facebook Page — the path that actually worked |
| Google NL | `clients/google_nl.py` | comment sentiment |
| LLM | `clients/llm.py` `OpenRouterLlmClient` | OpenAI-compatible; `OPENROUTER_MODEL` = any `:free` model |
| X | `clients/socialdata.py` | SocialData.tools (paid) |
| Scraper | `clients/scraper.py` | Apify/SociaVault (paid) — broad public chatter the official API can't see |
| FCM | `clients/fcm.py` | spike push (Real not wired yet) |
| ManyChat | `api/webhooks_manychat.py` | inbound webhook, DM metadata only |

## 8. API endpoints (all read-only from DB/Redis except auth/webhook)
- `GET /health` — pg+redis status (200 even when degraded → honest, not crashy).
- `GET /api/politicians` — list + token_status (read from cache, no network).
- `GET /api/command-center/{id}` — overview: 24h totals, avg score, trend, spike, calibrating.
- `GET /api/identity/{id}` — top posts, audience.
- `GET /api/public-voice/{id}` — sentiment + platform breakdown, mention feed.
- `GET /api/trends/{id}` — top topics + 48h volume series.
- `GET /api/crisis/{id}` — active spike, recent spikes, dm count.
- `GET /api/geo/{id}` — per-city mentions/negative/avg-sentiment (India map).
- `GET /api/misinfo/{id}` — claim-volume misinformation flag.
- `GET /api/growth/{id}` — daily reach + engagement.
- `GET /api/ai-brief/{id}` — reads the worker-generated brief from cache (NO LLM call on read).
- `POST /api/ground-input` — manual ground-intelligence entry → unified mentions.
- `GET /api/export/{id}/mentions.csv` — CSV export.
- `GET /api/auth/meta/connect|callback` — Facebook-Page OAuth (for META_SOURCE=facebook).
- `POST /api/webhooks/manychat` — DM metadata receiver.

## 9. Frontend
- **Theme:** glassmorphism — cream/beige/brown palette (`tailwind.config.js`), warm gradient
  background + `.glass`/`.glass-card`/`.glass-soft`/`.kpi`/`.sheen` classes in `index.css`.
- **Shell:** glass sidebar + top bar (account selector + backend-health dot). `PoliticianContext`
  loads accounts and holds the selected one. `useData` hook fetches per selected id (skips until id exists).
- **Modules:** Command Center (rich overview: KPI row, gauge=24h avg, sentiment donut, platform split,
  trend, top topics), Your Identity (interactive India map + reach/engagement + audience + posts table
  + CSV), Public Voice (sentiment feed), Trends (topics + volume), Crisis & DMs (spikes + DMs + misinfo),
  AI Brief, Ground report, Connect Instagram.
- **India map** (`components/IndiaMap.tsx`): pure SVG, projects lat/lon onto India's bounding box,
  bubble size = volume, color = sentiment. **Zoom** (+/−/reset) and **hover** → glass detail panel.

## 10. The real-account connection journey (important lessons)
Connecting a real account exposed Meta's worst friction; here's the resolved path and why:
- Personal IG accounts get **nothing** from the API — must convert to **Business/Creator** (free).
- The **Facebook-Page Graph path** (`META_SOURCE=facebook`) requires the IG account linked to a
  Facebook Page the user admins. The test account's token saw **0 Pages** despite all scopes granted
  (Meta's granular Page access / Accounts-Center linking ≠ a real admin Page). This blocked it.
- **Solution:** the newer **Instagram Login API** (`META_SOURCE=instagram_login`, `graph.instagram.com`)
  needs **no Facebook Page**. Generate an Instagram token from the app's *Instagram product →
  "Generate access token"* (requires adding the IG account as an **Instagram tester** in dev mode and
  accepting the invite). Then `python -m app.scripts.connect_ig_login` stores it. This WORKED.
- Diagnostics `app/scripts/diagnose_meta.py` (FB path) and `diagnose_ig.py` (IG path) print facts
  (token validity, scopes, pages, media_count) without exposing secrets — use them to debug connections.
- **App secret `client_credentials` failing (code 101)** is non-fatal — only used to long-live the
  token; the dashboard-generated IG token is already long-lived.

## 11. Bugs fixed during the build (so they don't recur)
- **Mentions could double-count** on re-ingestion → added `platform_mention_id` + unique constraint.
- **Test-DB URL** `.replace("/civicpulse",…)` corrupted the username → use `rpartition`.
- **Alembic** didn't import the custom `EncryptedString` type → import added + mako template.
- **Frontend null fetch:** `useData` fired before the politician list loaded → now skips until id exists.
- **Recharts gauge:** used cartesian `<YAxis>` inside `<RadialBarChart>` → use `<PolarAngleAxis>`.
- **Real ingestion pulled 0 posts:** `since` was the current hour (a bucket marker) used as the media
  time filter → now fetch latest 50 posts (no date filter); dedupe handles re-runs.
- **Command Center analytics:** counts showed only the latest hour (0% positive) → now 24h totals +
  gauge = day's average.
- **seed_demo crashed in real mode** (RealFcmClient NotImplemented) → seed forces Fake clients always.

## 12. What's intentionally NOT possible (per constitution — not bugs)
WhatsApp monitoring (no API — that's why Ground report exists), reading DM *content* (Meta blocks it —
only metadata via ManyChat), ward/pincode follower geo (Meta gives city-level only), free real-time X
(SocialData/Apify are paid).

## 13. Status — done vs pending
**Done & tested (62 tests, ruff/black/mypy clean):** WP1 foundation; WP2 ingestion + both Meta paths
(FB-Page OAuth + Instagram-Login); WP3 reaction sentiment + 0-100 aggregation + Command Center; WP4
India map + reach growth + audience snapshot; WP5 spike detection + dedupe (Fake FCM); WP6 ManyChat DM
webhook; WP8 Google NL sentiment; WP9 topics + X + Public Voice + Trends; WP10 geo inference +
misinformation; WP11 AI Brief (OpenRouter) + ground-input + CSV export. Glassmorphism UI across all pages.
Real account connected via Instagram-Login and 3 real posts ingested.

**Pending:** real FCM device push (WP5 live), PDF reports + admin panel (WP11 remainder), per-media IG
insights (reach/impressions), API auth/rate-limit + Sentry (prod hardening), and the deploy to
Vercel + Render + Supabase(Postgres) + Upstash(Redis) per `docs/DEPLOY.md`.

## 14. Demo vs real data
- **Demo account "Demo Netaji" (id=1)** — `python -m app.scripts.seed_demo` loads 8 days of rich data
  (diverse topics, 8 cities, a current-hour spike, an AI brief). This is the full "wow" experience.
- **Real account (id≥2)** — connected via OAuth/token; shows only what the API returns (e.g., a small
  creator account with no comments will look sparse — sentiment modules derive from comments).

## 15. Security notes
- Secrets via env only; `meta_token` encrypted at rest (Fernet); logs scrub sensitive keys.
- `.env`, `.venv`, `node_modules`, `tools/` are gitignored — verified no secrets are committed.
- Generate a FRESH `FERNET_KEY` for production; never reuse the dev one.
- Access tokens are secrets — never paste them in chat or commit them; put them in `.env` (gitignored).

## 16. Key commands
```powershell
# infra
pwsh infra/scripts/start-dev.ps1            # start pg+redis   (-Stop to stop)
# backend (from backend/, venv active)
alembic upgrade head
python -m app.scripts.seed_demo             # demo data
uvicorn app.main:app --port 8000
celery -A app.workers.celery_app:celery_app worker --pool=solo -l info
celery -A app.workers.celery_app:celery_app beat -l info
pytest -q ; ruff check app tests ; black --check app tests ; mypy app
# connect a real account (Instagram-Login path)
python -m app.scripts.connect_ig_login
python -c "from app.workers.tasks import ingest_all; print(ingest_all())"
# frontend (from frontend/)
npm run dev                                 # http://localhost:5173
```
