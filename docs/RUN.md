# RUN — AI Tech Consultant Capstone

## Repo layout

- `task1_knowledge_brain/` — Python FastAPI Knowledge Brain (:8000)
- `task2_inbox_agent/` — TypeScript Fastify Inbox Agent (:8100)
- `task3_meeting_to_scope/` — Python FastAPI Meeting-to-Scope (:8200)
- `tests/` — Task 1 unit tests
- `task3_meeting_to_scope/tests/` — Task 3 unit tests
- `task2_inbox_agent/tests/` — Task 2 unit tests
- `tests_integration/` — Mock-based integration tests (no live Claude, no live crawl)
- `tests_integration_live/` — Live-gated integration tests (require credentials)
- `scripts/start_all.sh` — starts all three services, waits for /health
- `docs/api/knowledge_brain.openapi.json` — the frozen contract
- `data/qa_fixtures/` — fixture QA answers for `KB_QA_CLIENT=fixture`

## Setup

cd ~/projects/ai-tech-consultant
python3 -m venv tech
source tech/bin/activate
pip install -r requirements.txt
(cd task2_inbox_agent && npm install --legacy-peer-deps && npm rebuild better-sqlite3 --legacy-peer-deps)

text

Node 22 is required (better-sqlite3 rebuilt for Node 22's NODE_MODULE_VERSION).

## Copy the env examples
mkdir -p .envs
cp env-examples/knowledge_brain.env.example .envs/.env.knowledge_brain
cp env-examples/inbox_agent.env.example .envs/.env.inbox_agent
cp env-examples/meeting_to_scope.env.example .envs/.env.meeting_to_scope

text

Set `KB_API_TOKEN_TASK2`, `KB_API_TOKEN_TASK3`, `KB_API_TOKEN_ADMIN` in `.envs/.env.knowledge_brain`.
Set the same `KB_BEARER_TOKEN` in `.envs/.env.inbox_agent` and `.envs/.env.meeting_to_scope`
to the corresponding Task 2 / Task 3 tokens.

## Start all three services
bash scripts/start_all.sh

text

The script:
- Activates `tech`,
- Starts Task 1, waits up to 30s for `/health`,
- Starts Task 2 (skipped if `node_modules` missing),
- Starts Task 3,
- Cleans up on Ctrl+C.

Logs are under `logs/task1.log`, `logs/task2.log`, `logs/task3.log`.

## Unit + mock integration tests
pytest tests -q
(cd task3_meeting_to_scope && pytest -q)
(cd task2_inbox_agent && npm test)
pytest tests_integration -v --deselect tests_integration/test_start_all_smoke.py
RUN_SMOKE=1 pytest tests_integration/test_start_all_smoke.py -v

text

Expected:
- Task 1: 59 passed
- Task 3: 58 passed
- Task 2: 44 passed
- Integration (no smoke): 15 passed
- Smoke: 1 passed

## Live tests (opt-in)

The live tests **skip** by default. They run only when ALL of the following are set:

- `CAPSTONE_LIVE=1`
- `ANTHROPIC_API_KEY`
- `CLAUDE_QA_MODEL` (for Task 1 live QA)
- Optionally `CLAUDE_CLASSIFIER_MODEL` and `CLAUDE_DRAFTER_MODEL` for the Task 2 live test

Example:
CAPSTONE_LIVE=1
ANTHROPIC_API_KEY=sk-ant-...
CLAUDE_QA_MODEL=claude-sonnet-4-5-20250929
CLAUDE_CLASSIFIER_MODEL=claude-sonnet-4-5-20250929
CLAUDE_DRAFTER_MODEL=claude-sonnet-4-5-20250929
pytest tests_integration_live -v

text

When live tests run, they write evidence files under `reports/live_<name>_<ts>.json`. That
file records the request, the response, and the Task 1 log path. It is the audit trail that
proves a live call happened.

**If Task 1's KB has no ingested content, live `/query` returns `insufficient_evidence` and
the live tests skip with a message telling you to run ingestion first. This is honest — the
capstone has never performed a live crawl, so the KB is empty by default.**

## What is not exercised

- Live crawl of `support.brilliantdirectories.com` — never performed. Ingestion tests use
  fixtures.
- Live Claude — exercised only under the gate above with your credentials.
- Real customer emails or client proposals — simulated only. All deliveries are labeled
  `is_simulated: true`.
- Browser UI error rendering — Task 2's review form only has a loading indicator; failed
  POSTs surface as raw JSON.

## Quick demo (one command)

    bash scripts/demo.sh

Then open in a browser:

    http://localhost:9000/dashboard.html

The demo script:
- Loads `.envs/` for all three services.
- Starts Task 1 (port 8000), Task 2 (port 8100), Task 3 (port 8200).
- Starts a small Python server on port 9000 that serves `docs/dashboard.html`
  with your Task 2 and Task 3 bearer tokens auto-injected from `.envs/`.
- Prints the URL when all three services are healthy.

Then in the browser:
- **Task 1**: type a question (e.g. `How do I import members via CSV?`) and click Ask.
  A cited answer appears, or an honest `insufficient_evidence` if the KB has no match.
- **Task 2**: pending drafts load automatically. Click any to open the full review UI.
- **Task 3**: `project_website` is pre-filled. Click Load project to see requirements
  and open questions from the baseline fixtures.

Press `Ctrl+C` to stop everything.

### How tokens are injected

The dashboard server (`scripts/serve_dashboard.py`) reads `.envs/.env.knowledge_brain`
and `.envs/.env.meeting_to_scope`, substitutes the token values into the HTML at serve
time, and returns the result. **Tokens are never written to disk.** They exist only in
the served HTTP response.

**This is safe only because the dashboard is opened on `localhost` by the same person
who has the tokens.** If the served HTML is ever exposed to a network, or the browser
page is saved to disk, the tokens are exposed. See "CORS and tokens — demo limitations"
in `OPERATIONS.md`.

### Fallback: no tokens injected

If `scripts/serve_dashboard.py` is not used (e.g. the static file is opened directly),
the token inputs will be empty and the reviewer must paste them. `docs/dashboard.html`
is still usable as a static file — it just requires manual token entry.

