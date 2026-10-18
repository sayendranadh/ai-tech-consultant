# AI Tech Consultant — Three-Agent Capstone

Three services that answer support questions with citations, draft
support replies for human approval, and turn meeting transcripts into
project scope documents.

## Prerequisites

- Node.js ≥ 22
- Python ≥ 3.11
- An Anthropic API key (`ANTHROPIC_API_KEY`)
- Ports 8000, 8100, 8200 free

## Configuration

Copy `.env.example` to `.env` and fill in:

    ANTHROPIC_API_KEY=sk-ant-...
    CLAUDE_PROMPT_VERSION=v2
    CLAUDE_CLASSIFIER_MODEL=claude-haiku-5-5
    CLAUDE_DRAFTER_MODEL=claude-haiku-5-5
    T2_DB_PATH=./task2_inbox_agent/data/task2.sqlite3
    T3_DB_PATH=./task3_meeting_to_scope/data/task3.sqlite3

Per-service env templates also exist in `env-examples/`.

## Setup

    python3 -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    (cd task2_inbox_agent    && npm install)
    (cd task3_meeting_to_scope && npm install)

## One-command startup

    ./scripts/start_all.sh

Starts all three services:

    Task 1 (Knowledge Brain):  http://127.0.0.1:8000
    Task 2 (Inbox Agent):      http://127.0.0.1:8100
    Task 3 (Meeting-to-Scope): http://127.0.0.1:8200

Health check:

    curl -s localhost:8000/health
    curl -s localhost:8100/health
    curl -s localhost:8200/health

Task 1 reports `status: degraded` when the vision model is mocked —
this is expected in the current environment (see `EVALS.md`).

## Run evaluations

    python3 scripts/run_evals.py --task task1 --live --split both
    python3 scripts/run_evals.py --task task2 --live --split both
    python3 scripts/run_evals.py --task task3 --live --split both   # not yet run

Results are written to `reports/eval_<UTC-timestamp>/`.

## Tests

    pytest tests/ tests_integration/ -q              # Python side
    (cd task2_inbox_agent    && npm test)            # Jest
    (cd task3_meeting_to_scope && npm test)          # Jest

## Documentation

- `DESIGN.md` — architecture, data flow, trade-offs (or `docs/DESIGN.md`)
- `EVALS.md` — measured results, trajectory, known failures
- `AI_LOG.md` — AI assistant prompts and one rejection
- `docs/OPERATIONS.md` — runbook
- `docs/RUN.md` — operational walkthrough
