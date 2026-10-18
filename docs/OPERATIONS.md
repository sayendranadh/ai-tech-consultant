# Operations — Task 1 Ingestion (Milestone 1A)

## Manual run (pilot, 3 pages)
    source tech/bin/activate
    python -m task1_knowledge_brain.ingestion --limit 3

## Dry run
    python -m task1_knowledge_brain.ingestion --limit 10 --dry-run

## Status
Milestone 1A exposes ingestion status only through the `manifest` table
(HTTP `/ingestion/status` arrives in Milestone 1C).

Inspect:
    sqlite3 data/knowledge_brain.sqlite3 \
      "SELECT processing_status, COUNT(*) FROM manifest GROUP BY processing_status;"

## Daily scheduling
NOT YET IMPLEMENTED — arrives in Milestone 1D.

## Operational status statement
> Daily ingestion is NOT operational. Milestone 1A implements the
> pipeline and unit tests only. No scheduler is running. No real crawl
> against support.brilliantdirectories.com has been performed by this
> delivery. See REPORT.md for actual test outcomes.

## Milestone 1B — Retrieval and QA

### Build real embeddings (manual; not run by tests)
    python -m task1_knowledge_brain.retrieval.index

### Run the QA eval dataset (mock mode — no live calls)
The eval dataset at `eval/qa_cases_v1.jsonl` is a **dataset only**. The
`live_run` field is `null` for every case. Do not interpret mock-mode outputs
as eval outcomes.

### Mocked capabilities
- Vision model: **SIMULATED**. Every stored description has status `simulated`
  and `model_id = "mock-vision/v1"`. No real Claude call occurs.
- QA model: **SIMULATED**. `MockQAClient` returns canned output; abstain
  logic is exercised but real model behavior is unverified.

### To go live (once credentials are available)
1. Set `ANTHROPIC_API_KEY` and the exact Claude model IDs in `.env`.
2. Construct `ClaudeVisionClient(model_id=...)` and a live `QAClient`.
3. Re-run `python -m task1_knowledge_brain.retrieval.index` and fill
   `live_run` fields in the eval dataset with **actual** results.

## Milestone 1C — HTTP service

### Run
    source tech/bin/activate
    python -m task1_knowledge_brain.service

### Export OpenAPI contract
    python -m task1_knowledge_brain.service.export_openapi
    # writes docs/api/knowledge_brain.openapi.json

### Auth
Set in `.env`:
    KB_API_TOKEN_TASK2=...
    KB_API_TOKEN_TASK3=...
    KB_API_TOKEN_ADMIN=...
Missing tokens cause 401 on every authenticated endpoint. Admin token required for
`/ingestion/run` and `/escalations/{id}/resolve`.

### Curl examples
    curl -s -H "Authorization: Bearer $KB_API_TOKEN_TASK2" \
      -H "Content-Type: application/json" \
      -d '{"question":"How do I reset a password?"}' \
      http://127.0.0.1:8000/query

    curl -s -H "Authorization: Bearer $KB_API_TOKEN_ADMIN" \
      -H "Content-Type: application/json" \
      -d '{"mode":"pilot","pilot_limit":3}' \
      http://127.0.0.1:8000/ingestion/run

## Milestone 1D — Daily incremental ingestion

### Run manually (pilot)
    python -m task1_knowledge_brain.scheduler --limit 3

### Run manually (dry run)
    python -m task1_knowledge_brain.scheduler --dry-run

### Enable in-process scheduler
Set in `.env`:
    KB_SCHEDULER_ENABLED=true
    KB_INGESTION_CRON_HOUR=2
    KB_INGESTION_CRON_MINUTE=0
Then start the service:
    python -m task1_knowledge_brain.service

### Inspect status
    curl -H "Authorization: Bearer $KB_API_TOKEN_TASK2" http://127.0.0.1:8000/ingestion/status

### Recover after crash
Recovery runs at service startup automatically. Or manually:
    python -c "from task1_knowledge_brain.ingestion.config import IngestionConfig; \
               from task1_knowledge_brain.scheduler.recovery import recover_interrupted; \
               print(recover_interrupted(IngestionConfig()))"

### Promote an approved answer
    curl -X POST -H "Authorization: Bearer $KB_API_TOKEN_ADMIN" \
      -H "Content-Type: application/json" \
      -d '{"expert_answer":"Open settings, then reset.","approved_for_general_knowledge":true,"approved_for_customer_specific":false}' \
      http://127.0.0.1:8000/escalations/<id>/resolve
Then (1D wires this automatically at resolve time; for now, run manually):
    python -c "from task1_knowledge_brain.ingestion.config import IngestionConfig; \
               from task1_knowledge_brain.retrieval.embedder import MockEmbedder; \
               from task1_knowledge_brain.scheduler.promotion import promote_escalation; \
               print(promote_escalation(IngestionConfig(), MockEmbedder(), '<id>', 1))"

### OPERATIONAL STATUS — NOT OPERATIONAL
> Daily ingestion is NOT operational in the runtime environment.
> - Scheduler code is implemented and unit-tested.
> - Tests use mocked HTTP (httpx.MockTransport) and temporary SQLite DBs.
> - No real crawl has been performed against support.brilliantdirectories.com.
> - No APScheduler trigger has fired against a real DB in a running service.
> - To verify: set KB_SCHEDULER_ENABLED=true, start the service, wait for the
>   cron window, and inspect /ingestion/status. Until then this statement stands.

## Task 2 — Inbox Agent (Milestone 2A)

### Setup
    cd task2_inbox_agent
    npm install
    npm run generate:kb-types
    npm run build

### Run (dev)
    T2_DB_PATH=./data/task2.sqlite3 KB_BEARER_TOKEN=<task2 token> npm run dev

### Process a single email
    curl -X POST http://127.0.0.1:8100/pipeline/process \
      -H 'Content-Type: application/json' \
      -d '{"email_id":"syn-0001"}'

### Dataset coverage
    npm run dataset:coverage

### Operational status
Task 2A is NOT OPERATIONAL against live models or a real Task 1 service.
Classifier and drafter are mocked; KB is exercised only via mock HTTP in tests.
No live crawl, no live model call, no real email sent.

## Task 2 — Review interface (2B)

### Run
    cd task2_inbox_agent
    npm install --legacy-peer-deps
    npm install @fastify/formbody@^8.0.0 --legacy-peer-deps
    npm run build
    T2_DB_PATH=./data/task2.sqlite3 KB_BEARER_TOKEN=<task2 token> npm run dev

### Populate some drafts
    curl -X POST http://127.0.0.1:8100/pipeline/process \
      -H 'Content-Type: application/json' \
      -d '{"email_id":"syn-0001"}'

### Review
    open http://127.0.0.1:8100/review

### 20-consecutive rule
    # inspect
    curl http://127.0.0.1:8100/admin/autonomy/how_to | jq
    # enable (admin; only sets eligibility flag — does NOT auto-send)
    curl -X POST http://127.0.0.1:8100/admin/autonomy/how_to/enable \
      -H 'Content-Type: application/json' \
      -d '{"actor":"admin@x","reason":"20 consecutive unchanged approvals"}'
    # kill switch
    curl -X POST http://127.0.0.1:8100/admin/autonomy/how_to/disable \
      -H 'Content-Type: application/json' \
      -d '{"actor":"admin@x","reason":"suspected regression"}'

### Feedback analysis
    # Query via the DAO from node REPL or a script; no HTTP endpoint yet.
    # The query is `Dao.repeatedCorrections(limit)`.

### Operational status
Review UI and 20-consecutive rule are **NOT OPERATIONAL in a live environment**:
- No real email is sent (simulated adapter only).
- No live Claude call (classifier/drafter still mocked).
- The `enableAutonomy` flag does not trigger any autonomous behavior — no
  auto-send code path exists in this milestone.

## Dashboard demo — tokens and CORS

### One-command demo

    bash scripts/demo.sh
    # then open http://localhost:9000/dashboard.html

### Token handling in the demo

The demo server (`scripts/serve_dashboard.py`) reads `.envs/*` and injects the
Task 2 and Task 3 bearer tokens into the HTML `<input>` fields at serve time.
Tokens are not written to `docs/dashboard.html` on disk. They appear only in
the served response, in the `value` attribute of two inputs.

### Why this is safe — and when it is not

Safe: the dashboard is opened by the same reviewer who has the tokens, on
`localhost`. The tokens never traverse a network beyond the local loopback.

**NOT safe:**
- If `scripts/serve_dashboard.py` is exposed on `0.0.0.0` and reachable from
  another machine.
- If the browser page is saved to disk (Ctrl+S) or shared as a file.
- If the dashboard is served from a public origin.

For production, replace this with a proper server-side session: the dashboard
authenticates once, the server holds the token, the browser never sees it.

### CORS recap

All three services have `allow_origins=["*"]` for the demo. This is a demo
configuration, not a production configuration. In production, restrict
`allow_origins` to the exact origin serving the dashboard.

