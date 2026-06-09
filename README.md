# CivicPulse

Social-media intelligence dashboard for Indian politicians — unified public sentiment,
constituency trends, crisis spike alerts, and a daily AI brief across Instagram, Facebook, and X.

> Architecture in one line: a **Celery worker** does ALL external fetching on a schedule and
> writes pre-computed aggregates to **Postgres + Redis**; the **dashboard reads only from our DB**,
> never from Meta/X on page load. See [`CLAUDE.md`](CLAUDE.md) and [`docs/BUILD_PLAN.md`](docs/BUILD_PLAN.md).

Current status: **WP1 (Foundation)** complete. Modules WP2–WP11 are stubbed shells.

---

## Run locally from a fresh clone (< 10 minutes, no Docker)

Prereqs already on this machine: **Python 3.11**, **Node 18+**, **PostgreSQL 17** (client+server),
**PowerShell**. Docker is intentionally not used locally.

### 1. Provision the native stack (Postgres cluster + Redis)
```powershell
pwsh infra/scripts/start-dev.ps1
```
This creates an isolated Postgres cluster in `tools/pgdata` on **port 5433** (no password prompt,
does not touch your system PostgreSQL), downloads a portable Redis, starts both, and writes a `.env`
with a fresh `FERNET_KEY`. (If Redis can't auto-download, install [Memurai](https://www.memurai.com)
or drop `redis-server.exe` into `tools/redis/` and re-run.)

### 2. Backend
```powershell
python -m venv backend/.venv
backend/.venv/Scripts/Activate.ps1
pip install -e "backend[dev]"

cd backend
alembic upgrade head                         # creates all 5 tables
uvicorn app.main:app --reload --port 8000    # http://localhost:8000/health  → {"status":"ok"}
```

**Seed demo data (so the dashboard is full of realistic content, offline):**
```powershell
python -m app.scripts.seed_demo
# -> Seeded politician id=1 'Demo Netaji' | buckets=97 | current-hour spike=True ...
```
This creates 8 days of mentions + post metrics and a current-hour negative spike (which
fires one Fake FCM push). `USE_FAKE_CLIENTS=true` means no real API keys are needed.

In two more terminals (from `backend/`, venv active) start the worker + scheduler to keep
ingesting on a 30-minute cadence (uses the Fake Meta client in demo mode):
```powershell
celery -A app.workers.celery_app:celery_app worker --pool=solo -l info   # --pool=solo on Windows
celery -A app.workers.celery_app:celery_app beat -l info
```

### 3. Frontend
```powershell
cd frontend
npm install
npm run dev            # http://localhost:5173
```
Open http://localhost:5173 — the **Command Center** shows a live sentiment gauge, 24h trend,
counts, and a red spike banner; **Your Identity** shows top posts + audience-by-city; **Crisis
& DMs** shows the active spike. Public Voice / Trends / AI Brief are stubs (WP9/WP11).

---

## Verify WP1
```powershell
# backend tests (DB tests auto-skip if Postgres is down)
cd backend; pytest -q

# lint / format / types
ruff check . ; black --check . ; mypy app

# frontend production build
cd ../frontend; npm run build
```

## Project layout
See [`docs/BUILD_PLAN.md`](docs/BUILD_PLAN.md) for the full monorepo layout and the WP1–WP11 plan.

## Environment variables
Every variable is documented in [`.env.example`](.env.example). Never commit a real `.env`.
Secrets (`meta_token`, API keys) are encrypted at rest (Fernet) and scrubbed from logs.

## Stopping the local stack
```powershell
pwsh infra/scripts/start-dev.ps1 -Stop
```
