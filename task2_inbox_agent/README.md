# Task 2 — Inbox Agent (Milestone 2A)

## Setup (from `task2_inbox_agent/`)

    npm install
    npm run generate:kb-types       # from ../docs/api/knowledge_brain.openapi.json
    npm run build                   # tsc --noEmit

Copy `.env.example` to `.env` and set at minimum:
- `KB_BEARER_TOKEN` — a Task 2 bearer token from Task 1's `.env`.
- `T2_DB_PATH` — defaults to `./data/task2.sqlite3`.

## Tests

    npm test

## Dataset coverage report (based on the actual file, not an accuracy claim)

    npm run dataset:coverage

## What 2A does NOT do

- No review UI, no approve/edit/reject/escalate endpoints (2B).
- No 20-consecutive-unchanged-draft counting (2B).
- No unauthorized-commitment blocking (2B enforces; 2A detects).
- No 50-email batch run (2C).
- No live Claude calls (mocked classifier + drafter; live classes raise
  `UnconfiguredModelError` until `ANTHROPIC_API_KEY` and model IDs are set).

## Operational status

2A is **NOT OPERATIONAL** against live models or a real Task 1 service.
Test suite uses mock HTTP transports and in-memory SQLite. Real Task 1 and
Claude calls remain unverified.
