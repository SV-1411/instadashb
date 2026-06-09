# ──────────────────────────────────────────────────────────────────────────
# CivicPulse — native local dev orchestrator (no Docker).
# Provisions a self-contained Postgres cluster + portable Redis under tools/,
# then prints the commands to start api / worker / beat.
#
#   Usage:  pwsh infra/scripts/start-dev.ps1
#           pwsh infra/scripts/start-dev.ps1 -Stop      # stop pg + redis
# ──────────────────────────────────────────────────────────────────────────
param([switch]$Stop)

$ErrorActionPreference = "Stop"
$Root      = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$Tools     = Join-Path $Root "tools"
$PgData    = Join-Path $Tools "pgdata"
$PgLog     = Join-Path $Tools "pg.log"
$RedisDir  = Join-Path $Tools "redis"
$PgPort    = 5433
$PgBin     = "C:\Program Files\PostgreSQL\17\bin"

function PgExe($name) { Join-Path $PgBin "$name.exe" }

if ($Stop) {
  Write-Host "Stopping Postgres + Redis..." -ForegroundColor Yellow
  if (Test-Path $PgData) { & (PgExe pg_ctl) -D $PgData stop -m fast 2>$null }
  Get-Process redis-server -ErrorAction SilentlyContinue | Stop-Process -Force
  Write-Host "Stopped." -ForegroundColor Green
  return
}

# ── 1. Postgres cluster ────────────────────────────────────────────────────
if (-not (Test-Path (Join-Path $PgData "PG_VERSION"))) {
  Write-Host "Initializing Postgres cluster (trust auth, port $PgPort)..." -ForegroundColor Cyan
  New-Item -ItemType Directory -Force -Path $PgData | Out-Null
  & (PgExe initdb) -D $PgData -U postgres -E UTF8 --auth=trust | Out-Null
}

$running = & (PgExe pg_isready) -p $PgPort -q; $isUp = ($LASTEXITCODE -eq 0)
if (-not $isUp) {
  Write-Host "Starting Postgres on port $PgPort..." -ForegroundColor Cyan
  & (PgExe pg_ctl) -D $PgData -l $PgLog -o "-p $PgPort" -w start
}

# Roles + databases (idempotent).
function PsqlPostgres($sql) { & (PgExe psql) -U postgres -p $PgPort -d postgres -tAc $sql }
$roleExists = PsqlPostgres "SELECT 1 FROM pg_roles WHERE rolname='civicpulse'"
if ($roleExists -ne "1") { PsqlPostgres "CREATE ROLE civicpulse LOGIN SUPERUSER PASSWORD 'civicpulse'" | Out-Null }
foreach ($db in @("civicpulse", "civicpulse_test")) {
  $dbExists = PsqlPostgres "SELECT 1 FROM pg_database WHERE datname='$db'"
  if ($dbExists -ne "1") { & (PgExe createdb) -U postgres -p $PgPort -O civicpulse $db }
}
Write-Host "Postgres ready: postgresql+psycopg://civicpulse:civicpulse@localhost:$PgPort/civicpulse" -ForegroundColor Green

# ── 2. Redis (portable, no install) ────────────────────────────────────────
$redisExe = Join-Path $RedisDir "redis-server.exe"
if (-not (Test-Path $redisExe)) {
  Write-Host "Fetching portable Redis for Windows..." -ForegroundColor Cyan
  $zip = Join-Path $Tools "redis.zip"
  $url = "https://github.com/tporadowski/redis/releases/download/v5.0.14.1/Redis-x64-5.0.14.1.zip"
  try {
    Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing
    Expand-Archive -Path $zip -DestinationPath $RedisDir -Force
    Remove-Item $zip -Force
  } catch {
    Write-Host "Could not download Redis automatically. Install Memurai (https://www.memurai.com) " -ForegroundColor Red
    Write-Host "or place redis-server.exe in $RedisDir, then re-run." -ForegroundColor Red
  }
}
$redisUp = (Test-NetConnection -ComputerName localhost -Port 6379 -WarningAction SilentlyContinue).TcpTestSucceeded
if (-not $redisUp -and (Test-Path $redisExe)) {
  Write-Host "Starting Redis on port 6379..." -ForegroundColor Cyan
  Start-Process -FilePath $redisExe -WindowStyle Hidden
}

# ── 3. .env bootstrap ──────────────────────────────────────────────────────
$envFile = Join-Path $Root ".env"
if (-not (Test-Path $envFile)) {
  Copy-Item (Join-Path $Root ".env.example") $envFile
  $key = & python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  (Get-Content $envFile) -replace "FERNET_KEY=.*", "FERNET_KEY=$key" | Set-Content $envFile
  Write-Host "Created .env with a fresh FERNET_KEY." -ForegroundColor Green
}

Write-Host "`nNext steps (run each in its own terminal, from backend/ with the venv active):" -ForegroundColor Yellow
Write-Host "  alembic upgrade head" -ForegroundColor Gray
Write-Host "  uvicorn app.main:app --reload --port 8000" -ForegroundColor Gray
Write-Host "  celery -A app.workers.celery_app:celery_app worker --pool=solo -l info" -ForegroundColor Gray
Write-Host "  celery -A app.workers.celery_app:celery_app beat -l info" -ForegroundColor Gray
