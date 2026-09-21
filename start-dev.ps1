# ─────────────────────────────────────────────────────────────────────────────
# start-dev.ps1 — One command to bring up the full Document-AI dev stack
# ─────────────────────────────────────────────────────────────────────────────
#
# Usage (from PowerShell):
#   .\start-dev.ps1
#
# What it starts (in order):
#   1. Docker infrastructure  — Postgres + Redis   (docker-compose.dev.yml)
#   2. Database migrations    — alembic upgrade head
#   3. Backend API            — uvicorn on :8000   (hot-reload enabled)
#   4. Dispatcher worker      — arq (Redis → Mistral Studio)
#   5. Workflow worker        — Mistral Studio activities
#   6. Frontend dev server    — Vite on :5173
#
# Press Ctrl+C to stop everything cleanly.
# ─────────────────────────────────────────────────────────────────────────────

$ErrorActionPreference = "Stop"

$ROOT_DIR   = Split-Path -Parent $MyInvocation.MyCommand.Definition
$BACKEND    = Join-Path $ROOT_DIR "backend-v2"
$FRONTEND   = Join-Path $ROOT_DIR "frontend-v2"
$PYTHON     = Join-Path $BACKEND "venv\Scripts\python.exe"

# ── Helpers ──────────────────────────────────────────────────────────────────
function Log($msg)  { Write-Host "[start-dev] $msg" -ForegroundColor Green }
function Warn($msg) { Write-Host "[start-dev] $msg" -ForegroundColor Yellow }
function Err($msg)  { Write-Host "[start-dev] $msg" -ForegroundColor Red }

# ── Pre-flight checks ────────────────────────────────────────────────────────
Log "Pre-flight checks..."

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Err "Docker is not installed or not in PATH."; exit 1
}
if (-not (Test-Path $PYTHON)) {
    Err "Python venv not found at $PYTHON"
    Err "Run: cd backend-v2; python -m venv venv; pip install -r requirements.txt"
    exit 1
}
if (-not (Test-Path (Join-Path $FRONTEND "node_modules"))) {
    Err "Frontend dependencies not installed. Run: cd frontend-v2; npm install"
    exit 1
}
if (-not (Test-Path (Join-Path $BACKEND ".env"))) {
    Err "Backend .env not found. Copy .env.example to .env and fill in your keys."
    exit 1
}

Log "All checks passed."

# ── Track background processes for cleanup ───────────────────────────────────
$script:bgProcesses = @()

# Recursively kill a process and all its descendants (children first)
function Kill-ProcessTree([int]$ParentId) {
    # Find all direct children of this process
    $children = Get-CimInstance Win32_Process -Filter "ParentProcessId=$ParentId" -ErrorAction SilentlyContinue
    foreach ($child in $children) {
        Kill-ProcessTree -ParentId $child.ProcessId
    }
    # Now kill the parent itself
    try {
        Stop-Process -Id $ParentId -Force -ErrorAction SilentlyContinue
    } catch {}
}

# Safety-net: kill any process still listening on the given port
function Kill-ByPort([int]$Port) {
    $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    foreach ($conn in $conns) {
        $pid_ = $conn.OwningProcess
        if ($pid_ -and $pid_ -ne 0) {
            Kill-ProcessTree -ParentId $pid_
            Log "Safety-net: killed PID $pid_ still on port $Port"
        }
    }
}

function Cleanup {
    Write-Host ""
    Warn "Shutting down all services..."
    foreach ($proc in $script:bgProcesses) {
        try {
            Kill-ProcessTree -ParentId $proc.Id
            Log "Stopped process tree for PID $($proc.Id)"
        } catch {}
    }
    # Safety-net: make sure ports 8000 and 5173 are freed
    Kill-ByPort -Port 8000
    Kill-ByPort -Port 5173
    Log "Stopping Docker containers..."
    docker compose -f "$ROOT_DIR\docker-compose.dev.yml" down 2>&1 | Out-Null
    Log "All services stopped."
}

try {
    [Console]::TreatControlCAsInput = $false
} catch {}

# ── Step 1: Docker infrastructure ────────────────────────────────────────────
Log "[1/6] Starting Docker infrastructure (Postgres + Redis)..."
docker compose -f "$ROOT_DIR\docker-compose.dev.yml" up -d
if ($LASTEXITCODE -ne 0) { Err "Docker compose failed."; exit 1 }

# Wait for healthy
Log "Waiting for containers to be healthy..."
$retries = 30
while ($retries -gt 0) {
    $status = docker compose -f "$ROOT_DIR\docker-compose.dev.yml" ps 2>&1 | Out-String
    if ($status -match "healthy") { break }
    Start-Sleep -Seconds 1
    $retries--
}
if ($retries -le 0) { Err "Docker services did not become healthy in time."; exit 1 }
Log "✅ Docker infrastructure is healthy."

# ── Step 2: Database migrations ──────────────────────────────────────────────
Log "[2/6] Running database migrations (alembic)..."
Push-Location $BACKEND
try {
    & $PYTHON -m alembic upgrade head 2>&1 | Out-Null
    Log "✅ Migrations applied."
} catch {
    Warn "⚠️  Migrations skipped (may already be up to date)."
}
Pop-Location

# ── Step 3: Backend API ──────────────────────────────────────────────────────
Log "[3/6] Starting Backend API (uvicorn :8000)..."
$api = Start-Process -FilePath $PYTHON `
    -ArgumentList "-m uvicorn main:app --host 0.0.0.0 --port 8000 --reload" `
    -WorkingDirectory $BACKEND `
    -PassThru -WindowStyle Normal
$script:bgProcesses += $api
Log "Backend API started (PID $($api.Id))"

Start-Sleep -Seconds 2

# ── Step 4: Dispatcher worker (arq) ─────────────────────────────────────────
Log "[4/6] Starting Dispatcher worker (arq)..."
$dispatcher = Start-Process -FilePath $PYTHON `
    -ArgumentList "-m arq worker.WorkerSettings" `
    -WorkingDirectory $BACKEND `
    -PassThru -WindowStyle Normal
$script:bgProcesses += $dispatcher
Log "Dispatcher started (PID $($dispatcher.Id))"

# ── Step 5: Workflow worker ──────────────────────────────────────────────────
Log "[5/6] Starting Workflow worker (Mistral Studio)..."
$worker = Start-Process -FilePath $PYTHON `
    -ArgumentList "workflow_worker.py" `
    -WorkingDirectory $BACKEND `
    -PassThru -WindowStyle Normal
$script:bgProcesses += $worker
Log "Workflow worker started (PID $($worker.Id))"

# ── Step 6: Frontend dev server ──────────────────────────────────────────────
Log "[6/6] Starting Frontend dev server (Vite :5173)..."
$frontend = Start-Process -FilePath "cmd.exe" `
    -ArgumentList "/c npm run dev" `
    -WorkingDirectory $FRONTEND `
    -PassThru -WindowStyle Normal
$script:bgProcesses += $frontend
Log "Frontend started (PID $($frontend.Id))"

Start-Sleep -Seconds 3

# ── Ready ────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "════════════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host "  🚀 Document-AI Dev Stack is running!" -ForegroundColor Green
Write-Host "════════════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host ""
Write-Host "  Frontend        →  " -NoNewline; Write-Host "http://localhost:5173" -ForegroundColor Cyan
Write-Host "  Backend API     →  " -NoNewline; Write-Host "http://localhost:8000" -ForegroundColor Cyan
Write-Host "  API Docs        →  " -NoNewline; Write-Host "http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "  Postgres        →  " -NoNewline; Write-Host "localhost:5432" -ForegroundColor Cyan
Write-Host "  Redis           →  " -NoNewline; Write-Host "localhost:6379" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Press Ctrl+C or close this window to stop." -ForegroundColor Yellow
Write-Host ""

# ── Wait & watch ─────────────────────────────────────────────────────────────
try {
    while ($true) {
        $anyRunning = $false
        foreach ($proc in $script:bgProcesses) {
            if (-not $proc.HasExited) { $anyRunning = $true; break }
        }
        if (-not $anyRunning) {
            Warn "All services have exited."
            break
        }
        Start-Sleep -Seconds 2
    }
} finally {
    Cleanup
}
