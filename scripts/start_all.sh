#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
source "$ROOT/tech/bin/activate"
mkdir -p "$ROOT/logs"
echo "==> Task 1 on :8000"
( cd "$ROOT" && python -m task1_knowledge_brain.service >"$ROOT/logs/task1.log" 2>&1 ) &
T1=$!
for i in $(seq 1 30); do
  curl -fsS "http://127.0.0.1:8000/health" >/dev/null 2>&1 && break
  sleep 1
done
T2=0
if [ -d "$ROOT/task2_inbox_agent/node_modules" ]; then
  echo "==> Task 2 on :8100"
  ( cd "$ROOT/task2_inbox_agent" && npm run dev >"$ROOT/logs/task2.log" 2>&1 ) &
  T2=$!
fi
echo "==> Task 3 on :8200"
( cd "$ROOT/task3_meeting_to_scope" && python -m src >"$ROOT/logs/task3.log" 2>&1 ) &
T3=$!
trap "kill $T1 $T2 $T3 2>/dev/null || true" INT TERM
echo "==> all started; Ctrl+C to stop"
wait
