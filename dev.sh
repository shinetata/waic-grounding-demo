#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

info()  { echo -e "${CYAN}[INFO]${NC} $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}   $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()   { echo -e "${RED}[ERR]${NC}  $*"; }

cleanup() {
  info "Shutting down..."
  [[ -n "${BACKEND_PID:-}" ]] && kill "$BACKEND_PID" 2>/dev/null && info "Backend stopped"
  [[ -n "${FRONTEND_PID:-}" ]] && kill "$FRONTEND_PID" 2>/dev/null && info "Frontend stopped"
  exit 0
}
trap cleanup SIGINT SIGTERM

# ---------- 1. Backend dependencies ----------
info "Installing backend dependencies..."
cd backend
if ! command -v uv &>/dev/null; then
  err "uv not found. Install: curl -LsSf https://astral.sh/uv/install.sh | sh"
  exit 1
fi
uv sync --extra render --quiet
ok "Backend deps ready"

# ---------- 2. Playwright browser ----------
if ! uv run python -c "from playwright.sync_api import sync_playwright" 2>/dev/null; then
  info "Installing Playwright Chromium..."
  uv run playwright install chromium
fi
ok "Playwright ready"

# ---------- 3. Render HTML → PNG ----------
info "Rendering screenshots..."
uv run python tools/render.py
ok "Screenshots rendered → assets/pages/"

# ---------- 4. Check .env ----------
if [[ ! -f .env ]]; then
  warn ".env not found, copying from .env.example"
  cp .env.example .env
  warn "Please edit backend/.env and set your API key"
fi

# ---------- 5. Start backend ----------
info "Starting backend on :8000..."
uv run uvicorn src.server:app --reload --port 8000 &
BACKEND_PID=$!
cd ..

# ---------- 6. Frontend dependencies ----------
info "Installing frontend dependencies..."
cd frontend
if ! command -v pnpm &>/dev/null; then
  err "pnpm not found. Install: npm install -g pnpm"
  exit 1
fi
pnpm install --silent
ok "Frontend deps ready"

# ---------- 7. Start frontend ----------
info "Starting frontend on :5173..."
pnpm dev &
FRONTEND_PID=$!
cd ..

# ---------- Done ----------
echo ""
ok "All services running:"
echo -e "   Frontend:  ${GREEN}http://localhost:5173${NC}"
echo -e "   Backend:   ${GREEN}http://localhost:8000${NC}"
echo -e "   Press ${YELLOW}Ctrl+C${NC} to stop all"
echo ""

wait
