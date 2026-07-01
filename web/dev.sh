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

# This is a fully independent project — it does not share dependencies, ports,
# or code with the ../backend / ../frontend static-screenshot demo.

# ---------- 1. Backend dependencies ----------
info "Installing backend dependencies..."
cd backend
if ! command -v uv &>/dev/null; then
  err "uv not found. Install: curl -LsSf https://astral.sh/uv/install.sh | sh"
  exit 1
fi
uv sync --quiet
ok "Backend deps ready"

# ---------- 2. Playwright browser ----------
info "Ensuring Playwright Chromium is installed..."
uv run playwright install chromium --quiet 2>/dev/null || uv run playwright install chromium
ok "Playwright ready"

# ---------- 3. Check .env ----------
if [[ ! -f .env ]]; then
  warn ".env not found, copying from .env.example"
  cp .env.example .env
  warn "Please edit web/backend/.env and set your API key"
fi

# ---------- 4. Start backend (owns the live browser session) ----------
info "Starting backend on :8010..."
uv run uvicorn src.server:app --reload --port 8010 &
BACKEND_PID=$!
cd ..

# ---------- 5. Frontend dependencies ----------
info "Installing frontend dependencies..."
cd frontend
if ! command -v pnpm &>/dev/null; then
  err "pnpm not found. Install: npm install -g pnpm"
  exit 1
fi
pnpm install --silent
ok "Frontend deps ready"

# ---------- 6. Start frontend ----------
info "Starting frontend on :5183..."
pnpm dev &
FRONTEND_PID=$!
cd ..

# ---------- Done ----------
echo ""
ok "All services running:"
echo -e "   Frontend:  ${GREEN}http://localhost:5183${NC}"
echo -e "   Backend:   ${GREEN}http://localhost:8010${NC}"
echo -e "   Press ${YELLOW}Ctrl+C${NC} to stop all"
echo ""

wait
