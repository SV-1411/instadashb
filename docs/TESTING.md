# Testing CivicPulse — full guide

There are two ways to test:
- **Demo mode** (default, `USE_FAKE_CLIENTS=true`) — no API keys, synthetic data, everything works
  offline. Use this to see every feature now.
- **Real mode** (`USE_FAKE_CLIENTS=false`) — your own Instagram account via OAuth + real API keys.

---

## 0. What you need (all already installed on this machine)
Python 3.11, Node 18+, PostgreSQL 17, PowerShell. Nothing else for demo mode.

## 1. Start everything from scratch (after a reboot)
Open **5 PowerShell terminals** (Postgres + Redis are started by the script; api/worker/beat are separate).

**Terminal 1 — infra (Postgres + Redis):**
```powershell
pwsh D:\POLITICIANDASHBOARD\infra\scripts\start-dev.ps1
```
Leave it; it provisions/starts the local Postgres cluster (:5433) and Redis (:6379).

**Terminal 2 — API:**
```powershell
cd D:\POLITICIANDASHBOARD\backend
.\.venv\Scripts\Activate.ps1
alembic upgrade head            # first time / after schema changes
python -m app.scripts.seed_demo # load demo data (re-runnable; refreshes the spike)
uvicorn app.main:app --port 8000
```

**Terminal 3 — Celery worker:**
```powershell
cd D:\POLITICIANDASHBOARD\backend ; .\.venv\Scripts\Activate.ps1
celery -A app.workers.celery_app:celery_app worker --pool=solo -l info
```

**Terminal 4 — Celery beat (scheduler):**
```powershell
cd D:\POLITICIANDASHBOARD\backend ; .\.venv\Scripts\Activate.ps1
celery -A app.workers.celery_app:celery_app beat -l info
```

**Terminal 5 — frontend:**
```powershell
cd D:\POLITICIANDASHBOARD\frontend
npm run dev
```
Open **http://localhost:5173**.

> You don't strictly need the worker/beat to look at the dashboard (the seed already populated it).
> They matter when you want the 30-minute ingestion cycle to keep refreshing data on its own.

## 2. Environment variables
- **Demo mode:** the repo `.env` already has a generated `FERNET_KEY` and `USE_FAKE_CLIENTS=true`.
  Nothing to add.
- **Real mode:** edit `.env` and set `USE_FAKE_CLIENTS=false` plus the keys you have:
  - `META_APP_ID`, `META_APP_SECRET`, `META_OAUTH_REDIRECT_URI` (see `docs/CONNECT_INSTAGRAM.md`)
  - `GOOGLE_NL_API_KEY` (comment sentiment)
  - `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` (AI Brief + topics; any `:free` model)
  - `SCRAPER_*` / `SOCIALDATA_API_KEY` + `X_QUERIES` (optional broad chatter / X)
  Every variable is documented in `.env.example`.

## 3. Manual test checklist (open http://localhost:5173)
| Page | What to check | Expected |
|------|---------------|----------|
| **Command Center** | gauge, 24h trend, counts, spike banner | score shown, red "active spike" banner, trend line |
| **Your Identity** | India bubble map, reach/engagement chart, audience bars, top posts, Export CSV | map bubbles over Indian cities; CSV downloads |
| **Public Voice** | sentiment + platform counts, mention feed with topic chips | feed of pos/neg/neutral mentions |
| **Trends** | top-topics bar chart, volume line | topics like events/roads/corruption |
| **Crisis & DMs** | spike banner, recent spikes, DM count, **misinformation card** | misinfo "elevated claim volume" flagged |
| **AI Brief** | summary + recommended actions | a short brief + 3 actions |
| **Ground report** | type "angry crowd about water in Pune" → Add | returns sentiment + topic "water" + city "Pune" |
| **Connect Instagram** | the OAuth button | in demo mode shows "Meta not configured" (expected) |

Top bar: account selector + a **backend health dot** (green = API+DB+Redis healthy).

## 4. Automated tests (proves the logic, incl. the spike alarm)
```powershell
cd D:\POLITICIANDASHBOARD\backend ; .\.venv\Scripts\Activate.ps1
pytest -q                                  # full suite (59 tests)
pytest tests/test_spike_detection.py -v    # the crown-jewel spike test
ruff check app tests ; black --check app tests ; mypy app   # quality gate
```

## 5. Quick API smoke test (no browser)
```powershell
curl http://localhost:8000/health
curl http://localhost:8000/api/command-center/1
curl http://localhost:8000/api/geo/1
curl http://localhost:8000/api/misinfo/1
```

## 6. Stop everything
```powershell
pwsh D:\POLITICIANDASHBOARD\infra\scripts\start-dev.ps1 -Stop   # stops pg + redis
```
Then Ctrl-C the api/worker/beat/frontend terminals.

## 7. Troubleshooting
- **Dashboard says "API unreachable"** → API terminal not running, or not on :8000.
- **`/health` shows `degraded`** → Postgres or Redis down; re-run `start-dev.ps1`.
- **Empty dashboard** → run `python -m app.scripts.seed_demo` again.
- **Celery on Windows errors** → must use `--pool=solo` (already in the commands above).
- **Port already in use** → an old process is still running; close it or reboot.
