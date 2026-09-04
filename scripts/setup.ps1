# =============================================================================
# Land Record Digitization System – Development Setup (Windows PowerShell)
# =============================================================================

$ErrorActionPreference = "Stop"
$ROOT_DIR = Split-Path -Parent $PSScriptRoot

Write-Host "🏛️  Setting up Land Record Digitization System…" -ForegroundColor Cyan

# ---- Environment file -------------------------------------------------------
if (-Not (Test-Path "$ROOT_DIR\.env")) {
    Copy-Item "$ROOT_DIR\.env.example" "$ROOT_DIR\.env"
    Write-Host "✅ Created .env from .env.example – review and update secrets." -ForegroundColor Green
} else {
    Write-Host "ℹ️  .env already exists, skipping." -ForegroundColor Yellow
}

# ---- Backend -----------------------------------------------------------------
Write-Host "`n📦 Setting up backend…" -ForegroundColor Cyan
Set-Location "$ROOT_DIR\backend"

if (-Not (Test-Path "venv")) {
    python -m venv venv
    Write-Host "✅ Created Python virtual environment." -ForegroundColor Green
}

& "$ROOT_DIR\backend\venv\Scripts\Activate.ps1"
pip install --upgrade pip -q
pip install -r requirements.txt -q
pip install -r requirements-dev.txt -q
Write-Host "✅ Backend dependencies installed." -ForegroundColor Green

# ---- Frontend ----------------------------------------------------------------
Write-Host "`n📦 Setting up frontend…" -ForegroundColor Cyan
Set-Location "$ROOT_DIR\frontend"
npm install
Write-Host "✅ Frontend dependencies installed." -ForegroundColor Green

# ---- Summary -----------------------------------------------------------------
Write-Host "`n🎉 Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "  Start services:    docker compose up -d"
Write-Host "  Run backend:       cd backend; .\venv\Scripts\Activate.ps1; uvicorn app.main:app --reload"
Write-Host "  Run frontend:      cd frontend; npm run dev"
Write-Host "  Run backend tests: cd backend; pytest"
Write-Host "  API docs:          http://localhost:8000/docs"
Write-Host "  Frontend:          http://localhost:3000"

Set-Location $ROOT_DIR
