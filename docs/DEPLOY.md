# Deploying CivicPulse

CivicPulse has 5 runtime pieces: **API** (FastAPI), **worker** (Celery), **beat** (Celery
scheduler), **PostgreSQL**, **Redis**. The frontend is a static React build.

## TL;DR — your chosen stack: Vercel + Render + Supabase
- **Frontend** → **Vercel** (free).
- **Backend** (api + worker + beat) → **Render** (3 services).
- **PostgreSQL** → **Supabase** (managed Postgres; free tier fine to start).
- **Redis** → **Upstash** (free tier). ⚠️ **Supabase has no Redis**, and Celery needs a Redis broker,
  so Redis lives on Upstash (or Render Key Value) — the one piece Supabase can't cover.
- **You do NOT need AWS/GCP.**

### Wiring the chosen stack
1. **Supabase**: create project → Settings → Database → copy the connection string and use it as
   `DATABASE_URL` with the psycopg driver + SSL, e.g.
   `postgresql+psycopg://postgres.<ref>:<pwd>@aws-0-<region>.pooler.supabase.com:5432/postgres?sslmode=require`.
   Run `alembic upgrade head` against it once.
2. **Upstash**: create a Redis DB → copy the `rediss://...` URL → set `REDIS_URL`,
   `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` to it (Upstash is TLS, `rediss://`).
3. **Render**: 3 services (api/worker/beat) from `backend/` with the env vars below.
4. **Vercel**: import `frontend/`, set `VITE_API_BASE_URL=https://<your-render-api>.onrender.com`.

> ⚠️ **Vercel can host ONLY the frontend.** It's serverless and cannot run the long-lived Celery
> worker/beat. Don't try to put the backend there.

---

## Option A — Render (recommended)

Create these from the Render dashboard (or a `render.yaml` blueprint):

| Render service | Type | Start command |
|---|---|---|
| `civicpulse-api` | Web Service | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| `civicpulse-worker` | Background Worker | `celery -A app.workers.celery_app:celery_app worker -l info` |
| `civicpulse-beat` | Background Worker | `celery -A app.workers.celery_app:celery_app beat -l info` |
| `civicpulse-db` | PostgreSQL | (managed) |
| `civicpulse-redis` | Key Value (Redis) | (managed) |

- Root dir = `backend/`. Build = `pip install -e .`.
- **Run migrations on deploy:** set the API service's pre-deploy command to `alembic upgrade head`.
- Set env vars (below) on all three backend services. Render injects `DATABASE_URL`/`REDIS_URL`
  when you attach the datastores — point `CELERY_BROKER_URL`/`CELERY_RESULT_BACKEND` at the Redis URL.
- Frontend: a **Static Site** (root `frontend/`, build `npm run build`, publish `dist/`), with
  `VITE_API_BASE_URL=https://civicpulse-api.onrender.com`. Or deploy `frontend/` to **Vercel**.

Cost: free tier sleeps (breaks the 30-min worker), so use the paid instances (~$7 each → ~$20–35/mo).

## Option B — VPS (cheapest)
1. Point a domain at the VPS, install Docker.
2. Put real values in `.env`, then `docker compose -f infra/docker-compose.yml up -d`.
3. Put **Caddy or Nginx** in front for HTTPS (Let's Encrypt). Serve the built `frontend/dist`.
4. Run `alembic upgrade head` once (the api container can do it on start).

## Option C — Railway / Fly.io
Same shape as Render: one service per process (api/worker/beat) + managed Postgres + Redis.

---

## Go-live checklist (env vars on the backend host)
Generate a **fresh** `FERNET_KEY` for production (don't reuse the dev one):
```
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
Required:
- `FERNET_KEY` — fresh
- `DATABASE_URL`, `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`
- `USE_FAKE_CLIENTS=false`
- `META_APP_ID`, `META_APP_SECRET`, `META_OAUTH_REDIRECT_URI=https://<your-api-domain>/api/auth/meta/callback`
- `GOOGLE_NL_API_KEY` (+ `NLP_SAMPLE_RATE`)
- `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` (a current `:free` model)
- `SCRAPER_PROVIDER`/`SCRAPER_API_KEY`/`SCRAPER_QUERIES` (optional), `SOCIALDATA_API_KEY`/`X_QUERIES` (optional)
- `FCM_SERVICE_ACCOUNT_JSON` (for real push)
- Frontend: `VITE_API_BASE_URL=https://<your-api-domain>`

Also:
- **Meta App** must be in **Live** mode + pass **App Review** for the IG permissions (Development mode
  only works for your own/test accounts).
- The OAuth redirect URI in the Meta App must EXACTLY match `META_OAUTH_REDIRECT_URI` (HTTPS, public).
- HTTPS is assumed end-to-end (Render/Vercel give it free; on a VPS use Caddy/Nginx + Let's Encrypt).
- Lock CORS in `app/main.py` to your frontend domain before going live.

## What's still needed before a real launch (tracked in FLAWS_AND_FIXES.md)
- Real FCM send (WP5 live), WP4 India map, WP10 geo/misinfo, WP11 reports/admin.
- API rate limiting + tighter CORS; Sentry/error tracking; a "Meta token expired" runbook.
