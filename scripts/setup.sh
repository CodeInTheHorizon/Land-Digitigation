#!/usr/bin/env bash
# =============================================================================
# Land Record Digitization System – Development Setup (Linux / macOS)
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo "🏛️  Setting up Land Record Digitization System…"

# ---- Environment file -------------------------------------------------------
if [ ! -f "$ROOT_DIR/.env" ]; then
  cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
  echo "✅ Created .env from .env.example – review and update secrets."
else
  echo "ℹ️  .env already exists, skipping."
fi

# ---- Backend -----------------------------------------------------------------
echo ""
echo "📦 Setting up backend…"
cd "$ROOT_DIR/backend"

if [ ! -d "venv" ]; then
  python3 -m venv venv
  echo "✅ Created Python virtual environment."
fi

source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
pip install -r requirements-dev.txt -q
echo "✅ Backend dependencies installed."

# ---- Frontend ----------------------------------------------------------------
echo ""
echo "📦 Setting up frontend…"
cd "$ROOT_DIR/frontend"
npm install
echo "✅ Frontend dependencies installed."

# ---- Summary -----------------------------------------------------------------
echo ""
echo "🎉 Setup complete!"
echo ""
echo "  Start services:    docker compose up -d"
echo "  Run backend:       cd backend && source venv/bin/activate && uvicorn app.main:app --reload"
echo "  Run frontend:      cd frontend && npm run dev"
echo "  Run backend tests: cd backend && pytest"
echo "  API docs:          http://localhost:8000/docs"
echo "  Frontend:          http://localhost:3000"
