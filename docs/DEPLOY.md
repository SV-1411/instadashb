# Deploying CivicPulse — FREE, no Docker

CivicPulse normally has 5 runtime pieces: **API** (FastAPI), **worker** + **beat** (Celery),
**PostgreSQL**, **Redis**. The blocker for a free deployment is the two always-on Celery
processes — free tiers sleep them, and Upstash's free Redis quota gets burned by an idle
worker polling the broker.

**This deployment removes Celery entirely.** `ingest_all()` (in `app/workers/tasks.py`) is a
plain function that runs the whole pipeline in one call, so instead of Celery beat we expose a
protected endpoint `POST /api/internal/run-ingestion` and have an **external cron (GitHub
Actions)** hit it every 30 minutes. That collapses the stack to **3 free pieces**:

| Piece | Host | Free terms |
|---|---|---|
| **Frontend** (static React) | **Vercel** | Free, auto-detects Vite, free HTTPS |
| **API** (FastAPI) | **Render** free Web Service | 750 hrs/mo; sleeps after 15 min idle (~50s cold start) |
| **Postgres** | **Neon** free | 0.5 GB, instant resume |
| **Redis** | **Upstash** free | used ONLY as cache + AI-brief store (low volume), NOT a Celery broker |
| **Scheduler** (replaces beat) | **GitHub Actions** | free cron POSTs the ingestion endpoint every 30 min |

No AWS/GCP. No Docker. $0/month.

---

## 0. The architecture change (already in the code)
- `app/api/internal.py` — `POST /api/internal/run-ingestion`, guarded by header
  `X-Cron-Secret: <CRON_SECRET>`. Runs `ingest_all()` synchronously and returns `{processed}`.
- `.github/workflows/ingest.yml` — cron (`*/30 * * * *`) + manual trigger; curls that endpoint.
- `render.yaml` — single web service blueprint (no worker, no beat).
- `backend/requirements.txt` — so Render's default `pip install -r requirements.txt` works.
- CORS now reads `CORS_ALLOW_ORIGINS` (your Vercel URL) on top of localhost.

The read API still never calls an external service (architecture rule 1 intact).

---

## 1. Neon (Postgres)
1. Create a project → copy the connection string.
2. Convert it to the psycopg driver CivicPulse uses (add `+psycopg`, keep `sslmode=require`):
   ```
   postgresql+psycopg://<user>:<pwd>@<host>.neon.tech/neondb?sslmode=require
   ```
   This is your `DATABASE_URL`.
3. **Create the tables + demo data** (run once, from your machine — see §6).

## 2. Upstash (Redis)
- In the Upstash console open your database → **Connect → "Redis" tab** (NOT "REST API").
- Copy the TLS Redis-protocol URL:  `rediss://default:<password>@<host>.upstash.io:6379`
- That is your `REDIS_URL`. ⚠️ The `UPSTASH_REDIS_REST_URL`/`REST_TOKEN` pair is a *different*
  HTTP interface and will NOT work with `redis-py` — you need the `rediss://` URL.

## 3. Render (API)
- New **Web Service** from the GitHub repo. **Root Directory:** `backend`.
- **Build:** `pip install -r requirements.txt`  (Render's auto-detected default — correct).
- **Start:** `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
  (runs idempotent migrations on each boot, then serves).
- **Health Check Path:** `/health`.
- **Environment** (Environment tab) — see the checklist in §5.

## 4. Vercel (Frontend)
- Import the repo. **Root Directory:** `frontend`. Framework preset: **Vite** (auto).
- Build `npm run build`, output `dist` (also in `frontend/vercel.json`, incl. SPA rewrite).
- Env var **`VITE_API_BASE_URL`** = `https://<your-render-app>.onrender.com`
  (a default is baked into `frontend/.env.production`; the dashboard value overrides it).

## 5. GitHub Actions (the cron that replaces Celery beat)
The workflow `.github/workflows/ingest.yml` is already in the repo. To make it run:
1. On GitHub: **Settings → Secrets and variables → Actions**.
2. Add a **secret** named `CRON_SECRET` = the same value you set on Render.
3. (Optional) Add a **variable** named `API_BASE_URL` = your Render URL
   (it defaults to `https://instadashb.onrender.com` if unset).
4. Trigger it once by hand: **Actions tab → "CivicPulse ingestion cron" → Run workflow**.
   After that it runs automatically every 30 min. (GitHub may delay scheduled runs a few
   minutes under load — fine for a 30-min cadence. The first call also wakes the sleeping dyno.)

## 6. Run migrations + seed demo data against Neon (the "where do I run this?")
From **your machine**, in `backend/` with the venv active, point `DATABASE_URL` at Neon and run:
```powershell
$env:DATABASE_URL = "postgresql+psycopg://<user>:<pwd>@<host>.neon.tech/neondb?sslmode=require"
$env:FERNET_KEY   = "<your-prod-fernet-key>"
alembic upgrade head                 # creates the 5 tables
python -m app.scripts.seed_demo      # loads "Demo Netaji" — 8 days of rich data + a spike
```
`alembic upgrade head` also runs automatically on every Render boot, so the seed is the only
truly manual step. Re-running `seed_demo` is safe (it upserts the demo tenant).

> ⚠️ **Neon pooler gotcha for migrations:** run `alembic upgrade head` against Neon's
> **direct (non-pooled)** endpoint — drop the `-pooler` segment from the host, e.g.
> `ep-xxxx-pooler.c-3.us-east-1...` → `ep-xxxx.c-3.us-east-1...`. DDL through the pooled
> endpoint (PgBouncer) can hang. The pooled URL is correct for the running app/`DATABASE_URL`;
> use direct only for the one-time migration + seed.

---

## Go-live env-var checklist (set on Render)
Generate a **fresh** Fernet key for prod (don't reuse the dev one):
```
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
Required:
- `DATABASE_URL` — Neon psycopg URL (§1)
- `REDIS_URL` — Upstash `rediss://` URL (§2)
- `FERNET_KEY` — fresh
- `CRON_SECRET` — random string; also added as a GitHub Actions secret (§5).
  Generate with `python -c "import secrets; print(secrets.token_urlsafe(32))"`
- `CORS_ALLOW_ORIGINS` — your Vercel URL, e.g. `https://instadashb.vercel.app`
- `USE_FAKE_CLIENTS=true` — full offline demo, no paid keys. Flip to `false` only after
  configuring real credentials below.

Optional (only when going past the demo):
- `OPENROUTER_API_KEY` (+ `OPENROUTER_MODEL` = a current `:free` model) — real AI Brief/topics.
- `META_APP_ID`/`META_APP_SECRET`/`META_OAUTH_REDIRECT_URI` + `META_SOURCE=instagram_login` —
  connect one real Instagram account (free; the no-Facebook-Page path — see `CONNECT_INSTAGRAM.md`).
- `GOOGLE_NL_API_KEY`, `SOCIALDATA_API_KEY`/`X_QUERIES`, `SCRAPER_*` — paid data sources.
- `FCM_SERVICE_ACCOUNT_JSON` — real push.

## Free-tier trade-offs (accept these)
- **Cold start ~50s** after idle; the 30-min cron + first user hit wake it. Add a 10-min
  `/health` ping if you want it always warm (still within the 750-hr budget).
- **Synchronous ingestion** runs inside the cron's HTTP request — seconds for the demo + a
  couple of accounts. At real scale, move back to a Celery worker (paid).

## Paid alternative (if you outgrow free)
Render paid: add `civicpulse-worker` (`celery -A app.workers.celery_app:celery_app worker -l info`)
and `civicpulse-beat` (`... beat -l info`) as Background Workers, point `CELERY_BROKER_URL`/
`CELERY_RESULT_BACKEND` at the Redis URL, and disable the GitHub Actions cron. ~$7/service.
