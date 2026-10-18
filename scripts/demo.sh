#!/usr/bin/env bash
# One-command demo: start all three services + the dashboard server with tokens
# auto-injected. Prints the URL to open. Ctrl+C shuts everything down.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ ! -d "$ROOT/tech" ]; then
  echo "ERROR: $ROOT/tech venv not found. Run: python3 -m venv tech && pip install -r requirements.txt" >&2
  exit 1
fi

if [ ! -d "$ROOT/.envs" ]; then
  echo "ERROR: $ROOT/.envs not found. See docs/RUN.md for how to set up env files." >&2
  exit 1
fi

source "$ROOT/tech/bin/activate"

# Load env for the services (dashboard server reads them directly from .envs).
set -a
if [ -f "$ROOT/.envs/.env.knowledge_brain" ]; then source "$ROOT/.envs/.env.knowledge_brain"; fi
if [ -f "$ROOT/.envs/.env.inbox_agent" ]; then source "$ROOT/.envs/.env.inbox_agent"; fi
if [ -f "$ROOT/.envs/.env.meeting_to_scope" ]; then source "$ROOT/.envs/.env.meeting_to_scope"; fi
set +a

export KB_QA_CLIENT="${KB_QA_CLIENT:-live}"

# Kill any stale processes on our ports.
pkill -f "task1_knowledge_brain.service" 2>/dev/null || true
pkill -f "tsx.*src/server.ts" 2>/dev/null || true
pkill -f "python -m src" 2>/dev/null || true
pkill -f "serve_dashboard.py" 2>/dev/null || true
sleep 2

LOG_DIR="$ROOT/logs"
mkdir -p "$LOG_DIR"

echo "==> starting the three services via scripts/start_all.sh"
bash scripts/start_all.sh >"$LOG_DIR/demo_services.log" 2>&1 &
SERVICES_PID=$!

echo "==> starting dashboard server on http://127.0.0.1:9000/dashboard.html"
python3 scripts/serve_dashboard.py --port 9000 --host 127.0.0.1 >"$LOG_DIR/demo_dashboard.log" 2>&1 &
DASHBOARD_PID=$!

# Wait for all three services.
for i in $(seq 1 90); do
  ok1=0; ok2=0; ok3=0
  curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1 && ok1=1
  curl -fsS http://127.0.0.1:8100/health >/dev/null 2>&1 && ok2=1
  curl -fsS http://127.0.0.1:8200/health >/dev/null 2>&1 && ok3=1
  if [ "$ok1" = 1 ] && [ "$ok2" = 1 ] && [ "$ok3" = 1 ]; then
    break
  fi
  sleep 1
  if [ "$i" = 90 ]; then
    echo "ERROR: services did not all become healthy in 90s" >&2
    tail -20 "$LOG_DIR/demo_services.log" >&2
    kill "$DASHBOARD_PID" 2>/dev/null || true
    kill "$SERVICES_PID" 2>/dev/null || true
    exit 1
  fi
done

# Wait for the dashboard server.
for i in $(seq 1 15); do
  if curl -fsS http://127.0.0.1:9000/dashboard.html >/dev/null 2>&1; then
    break
  fi
  sleep 1
  if [ "$i" = 15 ]; then
    echo "ERROR: dashboard server did not start on :9000" >&2
    tail -20 "$LOG_DIR/demo_dashboard.log" >&2
    kill "$DASHBOARD_PID" 2>/dev/null || true
    kill "$SERVICES_PID" 2>/dev/null || true
    exit 1
  fi
done

cleanup() {
  echo ""
  echo "==> shutting down"
  kill "$DASHBOARD_PID" 2>/dev/null || true
  kill "$SERVICES_PID" 2>/dev/null || true
  pkill -f "task1_knowledge_brain.service" 2>/dev/null || true
  pkill -f "tsx.*src/server.ts" 2>/dev/null || true
  pkill -f "python -m src" 2>/dev/null || true
  pkill -f "serve_dashboard.py" 2>/dev/null || true
  echo "==> stopped"
}
trap cleanup INT TERM

echo ""
echo "============================================================"
echo "  DEMO READY"
echo ""
echo "  Open in your browser:"
echo "    http://localhost:9000/dashboard.html"
echo ""
echo "  Tokens are pre-filled. Try:"
echo "    Task 1: type a question, click Ask"
echo "    Task 2: pending drafts load automatically"
echo "    Task 3: project_website is pre-filled; click Load project"
echo ""
echo "  Logs: $LOG_DIR/demo_services.log, $LOG_DIR/demo_dashboard.log"
echo ""
echo "  Press Ctrl+C to stop everything."
echo "============================================================"

wait
