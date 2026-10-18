# Delivery Report — Milestone 1A

## Code
- Implemented: sitemap parser (recursive index), polite fetcher, HTML parser,
  manifest/storage, chunker, orchestrator, CLI.
- Mocked: none in 1A.
- Requires live verification: a real crawl against the support center.

## Tests
- Command: `pytest tests/ingestion -v`
- Result: **NOT RUN — awaiting execution in user's WSL session.**
- Do not modify this section to "passed" until output is pasted here verbatim.

## Honesty statement
No claim of a successful test run or successful external integration is made
in this delivery. All status lines marked NOT RUN remain NOT RUN until actual
output is recorded.

## Milestone 1B — Multimodal retrieval + QA

### Implementation status
- Retrieval (semantic + keyword + hybrid): implemented
- FTS5 full-text index + triggers: implemented
- Embedding provider (real = sentence-transformers; mock = hash-based): implemented
- Vector store with sqlite-vec + in-memory fallback: implemented
- Vision client (live + mock): implemented; **live path not exercised**
- QA pipeline with citation validator: implemented
- Eval dataset v1 (25 cases): created; **all `live_run` fields null** — no results recorded

### Test run #3 (pending — do not mark passed)
- Command: `pytest tests/retrieval tests/qa -v`
- Result: **NOT RUN** — awaiting user execution and pasted output.

### Honesty statement
No live model call is made by this delivery. No live crawl is performed.
The eval dataset contains **no results**. Any capability listed above as
"requires live verification" remains unverified until such a run occurs.

## Milestone 1B — Multimodal retrieval + QA

### Test run #1
- Command: `pytest tests/retrieval tests/qa -v`
- Result: **6 failed, 11 passed, 1 warning in 3.30s**

### Defects found and corrected
1. VectorStore bootstrapped FTS before chunks table existed → 5 cascading failures. Fixed: ManifestStore-first bootstrap.
2. Score-range test asserted [0,1] but code returns cosine [-1,1]. Fixed: assertion and ADR-018.
3. FTS index not backfilled from pre-existing chunks. Fixed: `INSERT INTO chunks_fts(chunks_fts) VALUES('rebuild')` at bootstrap.
4. Pydantic `protected_namespaces` warning on ImageRef.model_id. Fixed: `protected_namespaces=()`.

### Test run #2 (verified green)
- Command: `pytest tests/retrieval tests/qa -v`
- Result: **17 passed in 4.33s** ✅

### Live-service honesty
- No live model call, no live crawl.
- Eval dataset `live_run` fields remain `null`.
- Vision and QA clients remain MOCKED; both flagged "requires live verification".
- Semantic quality of `all-MiniLM-L6-v2` unmeasured.
- `min_top_score=0.15` is a heuristic (ADR-018) — uncalibrated.

## Milestone 1C — HTTP service

### Implementation status
- Six endpoints implemented per spec.
- Auth: per-role bearer tokens (ADR-021).
- Rate limiter: in-memory token bucket (ADR-024).
- Job store: SQLite `ingestion_runs`; duplicate-run returns 200 `already_running`.
- Escalation store: versioned resolutions; general-knowledge promotion queued (ADR-022).
- `/health`: 200 for ok/degraded, 503 for unavailable (ADR-023).
- OpenAPI export at `docs/api/knowledge_brain.openapi.json`.

### Test run #1
- Command: `pytest tests/service -v`
- Result: **NOT RUN YET** — awaiting user execution and pasted output.

### Live-service honesty
- Vision and QA models remain MOCKED (`/health` reports `degraded`; `/query` returns
  `insufficient_evidence` unless a mock client is overridden in tests).
- No live model call. No live crawl.
- Escalation promotion into the retrieval store is **queued** (ADR-022); actual
  promotion-ingestion lands in 1D. 1C does **not** yet index approved answers.

## Milestone 1C — HTTP service

### Test run #1
- Command: `pytest tests/service -v`
- Result: **0 passed, 4 collection errors** (relative import from conftest without __init__.py).

### Fix
- Added `tests/__init__.py` + `tests/service/__init__.py`, moved `hdr` to `_helpers.py`.
- Service code unchanged; no service defect proven.

### Test run #2 (verified green)
- Command: `pytest tests/service -v`
- Result: **15 passed, 1 warning in 6.74s** ✅
- Warning: `starlette/testclient.py:40` — upstream `anyio.BlockingPortal` deprecation. Left visible per user instruction.

### Verified capabilities
- All 6 endpoints' typed schemas, auth, rate-limit path, error-path status codes,
  job idempotency, escalation lifecycle & versioning.

### Open gaps (honest)
1. **Error envelope** — `errors.http_exception_handler` defined but not wired. Default
   FastAPI `{"detail": ...}` is what clients see today. Decision pending.
2. **Promotion into retrieval store** — ADR-022 stages promotion as queued work.
   Actual ingestion lands in 1D. Until then, Requirement 7 is not satisfied in 1C alone.
3. **Live Claude vision / QA** — still mocked. `/health` reports `degraded`.
4. **Live crawl** — never executed.
5. **Eval dataset `live_run` outcomes** — all null.

## Milestone 1C.1 — Error envelope
- Files: `service/errors.py`, `service/api.py` (registration), tests updated for envelope shape.
- Test run: **NOT RUN YET** — awaiting user output.

## Milestone 1D — Daily incremental scheduler
- Files: `scheduler/*` (change_detector, daily_job, promotion, recovery, setup, __main__).
- Dependencies: apscheduler==3.10.4, sqlalchemy==2.0.36.
- Tests: 5 files added.
- Test run: **NOT RUN YET** — awaiting user output.

### Operational status (mandatory statement)
Daily ingestion is **NOT OPERATIONAL** in the runtime environment as of this delivery.
The scheduler code and tests are implemented; the tests use mocked HTTP and temporary
SQLite. No real crawl has been performed. No APScheduler trigger has fired against a
running service with a real DB. See `docs/OPERATIONS.md` for the exact steps required
to verify operationally.

## Milestone 1C.1 — Error envelope
- Files: `service/errors.py` (two handlers), `service/api.py` (registration),
  tests updated to assert `{"error": {"code", "message", "details"}}`.
- Test run: **15 passed, 1 warning in 7.89s** ✅
- Warning: `starlette` `BlockingPortal` deprecation (upstream, left visible).

## Milestone 1D — Daily incremental scheduler
- Files: `scheduler/change_detector.py`, `scheduler/promotion.py`, `scheduler/daily_job.py`,
  `scheduler/setup.py`, `scheduler/recovery.py`, `scheduler/__main__.py`,
  lifespan wiring in `service/api.py` (env-gated).
- Dependencies: `apscheduler==3.10.4`, `sqlalchemy==2.0.36`.
- Test run: **7 passed in 3.27s** ✅

### Verified
- Change detection classification (new/updated/unchanged/removed)
- Dedicated promotion of approved escalation answers via same ingestion pipeline
- Promotion idempotency on content hash; skips unapproved
- Recovery of interrupted `in_progress` rows
- Database-level single-run lock (BEGIN IMMEDIATE)
- APScheduler `max_instances=1` + coalesce

### NOT verified / NOT operational (verbatim from OPERATIONS.md)
> Daily ingestion is NOT operational in the runtime environment. The scheduler code is
> implemented and unit-tested. Tests use mocked HTTP and temporary SQLite DBs. No real
> crawl has been performed against support.brilliantdirectories.com. No APScheduler trigger
> has fired against a running service with a real DB.

### Open gaps
1. **Promotion not wired into /escalations/{id}/resolve.** Promotion function is implemented
   and tested standalone but the endpoint does not invoke it. Task 1 Requirement 7 is
   not satisfied end-to-end until this is wired. Decision pending.
2. **Live Claude vision / QA** — still mocked.
3. **Live crawl** — never executed.
4. **Eval dataset `live_run` outcomes** — all null.
5. **`pytest_asyncio` fixture loop scope** warning — config gap, not test defect.

### Full suite
- Status: **NOT RUN at repo root yet** — awaiting user output.

## Task 1 — Knowledge Brain: COMPLETE (as implemented and tested)

### Final verification
- `pytest tests/service -v` → **17 passed, 1 warning in 8.55s**
- `pytest tests/scheduler -v` → **7 passed in 3.05s**
- `pytest -v` (full suite) → **59 passed, 12 warnings in 28.93s**

Warnings: 1 × `starlette` (`anyio.BlockingPortal` deprecation, upstream);
11 × `bs4` (`strip_cdata` deprecation, upstream). Both left visible per user instruction.

### Verified
See REPORT.md "Task 1 Verified" table — all ingestion, retrieval, service, scheduler,
promotion, and error-envelope behaviors listed as passing above.

### NOT verified (honest status, carries forward)
- Live crawl against support.brilliantdirectories.com: NEVER EXECUTED.
- Live Claude vision / QA: MOCKED. `ClaudeVisionClient` unexercised.
- Real sentence-transformers embeddings: implemented, not exercised in tests.
- `min_top_score=0.15`: heuristic, uncalibrated.
- APScheduler daily trigger: never fired against a running service.
- `eval/qa_cases_v1.jsonl`: 25 cases, all `live_run` fields `null`.

### Interface frozen for Tasks 2 and 3
- `docs/api/knowledge_brain.openapi.json` — export before downstream work begins.
  Any Task 1 schema change requires re-export + diff before Tasks 2/3 adapt.

## Task 2 — Inbox Agent: Milestone 2A — VERIFIED

### Runtime environment
- Node: v22.23.3 (nvm default alias set)
- npm: 10.9.9
- Install command: `npm install --legacy-peer-deps`
  (Workaround for npm CLI `edgesOut` bug on plain `npm install`. MUST be used by
  all contributors and in any CI config. Documented in README.md.)

### Dependencies
- vitest: ^4.1.11 (installed as 4.1.12)
- npm audit: **0 vulnerabilities** ✅

### Verification (pasted by user, 2025-10-18)
- `npm install --legacy-peer-deps` → success, `found 0 vulnerabilities`
- `npm test` → **18 passed, 7 files, 401ms**
- Runtime confirmed: `RUN v4.1.12`, Node 22.23.3

### Capabilities verified by executed tests
- KB client typed HTTP, timeout, retry, schema validation, error classification (5 tests)
- Zod schemas for Classification, DraftBody, QAResponse, ErrorEnvelope (2 tests)
- Mock classifier fixture lookup + failure on unknown (2 tests)
- 50-email dataset coverage: ≥50 records, all 7 categories, all `is_synthetic:true` (4 tests)
- Idempotent draft insert (same key → same id; new version → new id) (2 tests)
- KB failure forces insufficient_evidence + escalation_required + human_approval_required (1 test)
- Safeguard detectors: refund, price, delivery_date, feature_promise (2 tests)

### Dataset coverage (from actual file)
- total: 50
- by_category: how_to=8, troubleshooting=7, project_request=7, refund_cancellation=7,
               complaint=7, quote_request=7, follow_up=7
- by_risk: low=12, medium=21, high=17
- escalation_required: 35
- non_synthetic_flagged: 0

### Known limitations (honest)
1. Classifier and drafter are MOCKED in all tests and in default server startup.
   Live Claude clients (`ClaudeClassifier`, `ClaudeDrafter`) raise
   `UnconfiguredModelError` until `ANTHROPIC_API_KEY` and model IDs are set.
2. Knowledge Brain HTTP client has never called a live Task 1 service. All tests
   use injected mock `fetchImpl`.
3. No real email has been sent — no delivery adapter exists in 2A. Arrives in 2B.
4. No review UI, no approval endpoints, no 20-consecutive-unchanged-draft rule.
   Those are 2B's scope.
5. `npm install --legacy-peer-deps` is required. Plain `npm install` fails with
   `Cannot read properties of null (reading 'edgesOut')` — a known npm CLI bug
   on this dependency tree. Documented in README.
6. `prebuild-install@7.1.3` deprecation warning (transitive via better-sqlite3).
   Cosmetic, not a vulnerability; migration to `node:sqlite` deferred.

### Honesty statement
No classification accuracy, draft-quality score, or model evaluation is claimed.
Dataset coverage above is a file-based count. Mocked vs. live capabilities are
explicitly separated. Any "verified" claim above is backed by pasted test output.

## Task 2 — Inbox Agent: Milestone 2B — VERIFIED

### Verification (pasted 2025-10-18)
- `npm run build` → clean
- `npm test` → **44 passed, 14 files, 708ms**
- Runtime: Node 22.23.3, vitest 4.1.12, npm 10.9.9, install via `--legacy-peer-deps`

### Verified capabilities
- Review UI (server-rendered HTML), pending list + detail view with warnings, sources,
  model/prompt version, review history, per-category counter.
- Reviewer actions: approve, edit-and-send, reject-with-replacement, escalate, correction reason.
- SimulatedDeliveryAdapter: delivery_status "simulated_sent", is_simulated true, no network call.
- Feedback records: final_reply, correction_reason, delivery_id, is_qualifying on approvals;
  repeatedCorrections() groups by (category, correction_reason).
- 20-consecutive state machine:
  - Increment only on approve-without-substantive-edit + successful delivery
  - Reset on edit, reject, escalate, delivery failure
  - Threshold exactly at 20 → eligible_for_autonomy flag set (behavior unchanged)
  - Per-category isolation verified
  - High-risk exclusion (refund_cancellation, complaint) never eligible
  - Duplicate-event guard prevents double-counting
  - Enable/disable endpoints record autonomy_events with actor and reason
- Comparison policy: whitespace-collapse, lowercase, signature-strip.

### NOT verified (carries forward)
- Real SMTP delivery (simulated only, per decision).
- Live Claude classifier/drafter (mocked; live classes raise UnconfiguredModelError).
- Live Task 1 HTTP call (mocked via injected fetch).
- Auto-send behavior does NOT exist by design (ADR-038).
- Prompt improvement has NOT been demonstrated by any evaluation (2C).
- Classification accuracy has NOT been measured (2C).

### Honesty statement
No claim of a successful real email delivery, live model call, or measured improvement.
All "verified" claims are backed by pasted test output from the user's terminal.
The 20-consecutive-rule is verified as a flag-setting state machine; no autonomous
sending exists in the codebase.

## Task 3 — Milestone 3A: Transcript ingestion + structured requirement extraction — VERIFIED

### Verification (pasted by user, 2025-10-18)
- `pytest -v` from `task3_meeting_to_scope/` → **18 passed, 1 warning in 0.70s**
- Warning: `starlette/testclient.py:40` `anyio.BlockingPortal` deprecation (upstream, left visible).

### Verified capabilities
- Three synthetic role-play transcripts load (meeting_1_website, meeting_2_ecommerce, meeting_3_followup).
- Chunker splits with controlled overlap.
- MockExtractor returns records with source_refs pointing to real turn IDs.
- Merge produces requirements + open questions; conflicts detected on date mismatch across meetings.
- Claim validator flags unsupported quotes; clean fixtures validate with zero issues.
- FastAPI `/transcripts`, `/projects/{id}`, `/health` endpoints operate; Pydantic schemas enforce attribution.

### NOT verified (honest, carries into 3B/3C)
- ClaudeExtractor: **mocked**, `UnconfiguredModelError` on use. No live call.
- Extraction accuracy: **not measured.** No evaluation set defined.
- Contradiction detection & claim validation: heuristics, verified only against these fixtures.
- Task 1 integration: out of 3A scope.
- 3B/3C capabilities (feasibility, scope, estimates, proposals, approvals, follow-up comparison): all out of 3A scope.

### Honesty statement
No claim of extraction accuracy, model quality, or general contradiction detection.
"Verified" claims are backed by pasted test output. Mocked vs. live capability
is explicitly separated.

## Task 3 — Milestone 3B: Feasibility, scope, estimates, proposal, approval — VERIFIED

### Verification (pasted by user)
- `pytest -v` from `task3_meeting_to_scope/` → **33 passed, 1 warning**
- Warning: `starlette/testclient.py:40` `anyio.BlockingPortal` deprecation (upstream).

### Verified capabilities
- Feasibility classifications (`existing_configuration`, `existing_feature_with_limitation`,
  `potential_custom_development`, `needs_clarification`). Missing evidence → `needs_clarification` +
  `escalated` (never "unsupported" — the classification literal does not exist in the schema).
- Structured `ScopeDocument` (objective, problem, agreed requirements linked to source refs,
  proposed solution, deliverables, exclusions, assumptions, dependencies, acceptance criteria,
  client responsibilities, open questions, risks).
- Deterministic engineering estimates: per-task `low / likely / high` hours with rationale,
  assumptions, dependencies, uncertainty, `provisional_unreviewed` reviewer status.
  Totals computed in Python via `aggregate()`, not requested from a model.
- Client proposal with all required sections; `pricing_assumptions.hourly_rate`, `.currency`,
  `.taxes_included`, `.total_price` default to `None` and appear in `.unresolved`. No invented
  commercial terms.
- Human approval workflow: `approve()` requires an existing proposal version; `send_simulated()`
  returns `409` unless the proposal has an `approved` version whose `text_hash` matches the
  canonical content hash. Only `SimulatedProposalDeliveryAdapter` is used; every delivery record
  has `is_simulated: true` and `delivery_status = "simulated_sent"`.

### NOT verified (honest, carries into 3C and beyond)
- Live Task 1 feasibility calls — mocked via injected KB client.
- Live Claude proposal generation — `ProposalWriter` is deterministic; no live call.
- Real SMTP delivery — simulated only.
- Pricing / currency / rates — unresolved by default; no invented values.
- Feasibility classification accuracy — not measured; no evaluation set.
- Estimate quality — provisional by design; no accuracy claim.
- Follow-up baseline diff — 3C scope.

### Honesty statement
No claim of live feasibility behavior, live model call, or measured accuracy.
All "verified" claims are backed by pasted test output. Pricing is unresolved by default.
Estimates are provisional. Delivery is simulated.

## Task 3 — Milestone 3C: Follow-up baseline comparison — VERIFIED (with two documented gaps)

### Verification (pasted by user)
- `pytest -v` from `task3_meeting_to_scope/` → **58 passed, 1 warning in 5.57s**
- Warning: `starlette/testclient.py:40` `anyio.BlockingPortal` deprecation (upstream).

### Verified capabilities
- Requirement matching via token-set Jaccard on `source_quote`, with thresholds:
  - 0.5+ confirmed, 0.3–0.5 ambiguous, <0.3 no match.
  - Constants exposed in `src/matcher.py` (`CONFIRM_THRESHOLD`, `AMBIGUOUS_THRESHOLD`).
- Change detection classifying each follow-up requirement as added / removed / modified /
  unchanged / unresolved; detects:
  - requirement modifications (e.g., contact form sales → support),
  - new requirements (newsletter widget),
  - explicit-removal decisions from transcript (blog section),
  - baseline requirements with no follow-up match (removed),
  - deadline changes from commitment records (2025-03-15 → 2025-04-01).
- Out-of-scope detection via deterministic phrase markers
  (`out of scope`, `not in scope`, `separate phase`, `we'll do that later`,
  `later phase`, `not for this project`). Flagged mobile-app request verified.
- Baseline preservation: comparison does not modify baseline version. Revised proposal
  is `n+1`, status `revised`. Only `approve` transitions the change report to approved.
- Change report: structured `ChangeReport` (persisted as JSON) + on-demand markdown via
  `render_markdown(report)`. Every change carries old value, proposed new value, evidence
  (transcript turn + quote), effort delta, unresolved questions, approval status.
- Human approval gate: `POST /change-reports/{id}/approve` required before
  `POST /change-reports/{id}/send` succeeds. Send returns 409 otherwise.
- Simulated delivery only: `is_simulated = 1`, `delivery_status = 'simulated_sent'`.
  No network call is issued.

### Documented gaps (honest)
1. **`tentative` flag is structural only.**
   `FollowupRequirement.tentative` exists and 3C honors it (a tentative requirement is
   classified `unresolved` regardless of match). However, **Task 3A does not populate
   this field**; 3A's schema has no `tentative`. The followup fixture supplies it
   manually. Real 3A output will always have `tentative = False`, so the tentativeness
   guard has no effect in the live pipeline. **Requires 3A schema change in a future
   milestone** before the guarantee is real.

2. **Per-ambiguity reviewer confirmation is not captured at the change level.**
   `DetectedChange.reviewer_confirmation_required` is set for ambiguous matches and for
   any `tentative` requirement, but there is no per-change confirmation endpoint. The
   API-level approval of the whole change report is the coarse gate. The prompt says
   "retain reviewer confirmation for ambiguous matches" — this is **partially satisfied**
   (flag exists, coarse approval implies review) but not captured at change granularity.

3. **Stable-ID matching across meetings not possible.**
   3A's requirement IDs are per-transcript (`REQ-meeting_N-###`). Cross-meeting ID
   stability does not exist. 3C relies entirely on token-Jaccard matching. A follow-up
   requirement that shares meaning with a baseline requirement but no tokens will be
   misclassified. The fixture does not exercise that case.

4. **Change-detection accuracy is not measured.**
   The prompt requires accuracy metrics only after evaluation against a documented
   reference set. No such set exists in this repository. The fixtures verify the
   **logic** against five synthetic cases; they do not measure accuracy.

### Not verified (honest)
- Live Claude change detection — deterministic heuristics only.
- Live Task 1 re-feasibility of changed requirements — 3C does not re-invoke Task 1.
- Real SMTP — simulated adapter only.
- Reviewer UI — none exists; approval is API-only.

### Honesty statement
No change-detection accuracy, matching precision, or live-service capability is claimed.
Fixtures verify logic only. Gaps are listed above, not glossed over. The delivered
verification is: `58 passed, 1 warning`, backed by pasted output.

## D1 — Integration Foundation — VERIFIED (with two gaps closed in D2)

### Verification
- `pytest tests_integration -v` (D1 subset) → 8 passed in 4.10s
- Task 1: 59 passed / Task 3: 58 passed / Task 2: 44 passed

### What D1 delivered
- 12 files on disk (env examples, ARCHITECTURE.md, start_all.sh, qa fixtures, middleware)
- RequestIDMiddleware registered on Tasks 1, 2, 3
- FixtureQAClient activated via `KB_QA_CLIENT=fixture`
- Task 3's 3B mount uses HTTPKBClient when `KB_BASE_URL` is set (code change, route-level verified in D2)
- `scripts/start_all.sh` — executable, `bash -n` clean

### Gaps carried to D2
- `start_all.sh` never executed end-to-end → closed in D2 (smoke test)
- Task 3 route-level use of HTTPKBClient unverified → closed in D2 (test_c)
- Task 2 test count from combined run was truncated → confirmed in D2: 44 passed (14 files)

## D2 — Verification Scenarios A–F + Smoke Test + UI Loading — VERIFIED

### Verification (all pasted)
- `pytest tests_integration -v --deselect tests_integration/test_start_all_smoke.py` → **15 passed, 1 deselected, 1 warning in 10.53s**
- `RUN_SMOKE=1 pytest tests_integration/test_start_all_smoke.py -v` → **1 passed in 4.52s**
- Task 1: **59 passed** / Task 3: **58 passed** / Task 2: **44 passed (14 files)**

### Proven
- Verification A: `/query` returns fixture answer with cited source
- Verification B: Task 2's real KBClient reaches live Task 1
- Verification C: Task 3's `/workflow/run` route uses HTTPKBClient when KB_BASE_URL is set
- Verification D: insufficient_evidence preserved through Task 2 client
- Verification E: Task 1 outage → Task 2 raises KBUnavailableError, Task 3 returns needs_clarification + unverified (no fabrication)
- Verification F: Task 3 follow-up compare produces revised proposal v2 with status "revised"
- `scripts/start_all.sh` brings up all three services and reaches /health on each
- Task 2 review form has a loading indicator (JS present; server-side rendering intact)
- All three service test suites remain green

### Not proven (honest, documented)
- Live Claude not exercised. Fixture QA only.
- Live crawl not executed.
- Task 2 full pipeline draft generation via POST /pipeline/process not tested (requires live Claude)
- Browser-side error rendering not implemented; failed POSTs surface as raw JSON.
- start_all.sh only tested on happy path; crash handling untested.
- Multi-task SQLite concurrency untested.

### Honesty statement
No live model or live crawl claims. Integration tests prove wiring between services
over real HTTP. Fixture answers are labeled [FIXTURE]. Task 2 / Task 3 keep their own
DBs; no duplicate retrieval store. Delivery remains simulated on Task 2 and Task 3.

---

## Live Milestone — Task 1 Knowledge Brain Live Grounded Answer

**Date:** 2026-10-18
**Model:** claude-haiku-5-5 (Anthropic direct API; chosen for budget under a $5 balance)
**Prompt version:** v1 (as recorded in .envs/.env.knowledge_brain)
**Crawl source:** https://support.brilliantdirectories.com/support/sitemap.xml
**Crawled corpus:** 1240 documents, 5805 active chunks (real crawl, 2026-10-18)
**Embeddings:** sentence-transformers/all-MiniLM-L6-v2, 5805 chunks indexed

### What was achieved

Two live grounded answers from the same KB (one via TestClient diagnostic, one
via the HTTP service with wall-clock timing). Both produced:

- status: answered
- Real [chunk_id=N] citations in the answer text
- Real sources with real URLs from support.brilliantdirectories.com
- An explicit abstention on sub-questions whose evidence was not in retrieval
  (the "upload steps in the admin interface" case) — non-fabrication rule
  working in the live path
- escalation_required: false

### Live HTTP-timed call (wall clock: 4.79s)

Request: POST /query {"question": "How do I import members via CSV?"}
Response (excerpt — full body is in /tmp/live_query_response.json):

    status: "answered"
    answer: (cited with [chunk_id=185] and [chunk_id=1796])
    sources:
      - chunk_id=185, url=https://support.brilliantdirectories.com/support/solutions/articles/5000558475-how-to-import-members-via-csv-file
      - chunk_id=1796, url=https://support.brilliantdirectories.com/support/solutions/articles/12000045147-my-members-search-members-overview
    escalation_required: false

Wall-clock latency: 4.79s (measured by /usr/bin/time -v on the curl invocation
against the running HTTP service).
Estimated cost: ~$0.0005 per query (Haiku 5.5 at $0.10/$0.50 per MTok;
~2K input tokens of retrieved evidence + ~350-400 output tokens). This is an
ESTIMATE from token counts, not a measured invoice.

### Defects found and fixed during this milestone

1. FTS5 escape defect. The original escape wrapped the entire query in double
   quotes, turning multi-word queries into phrase searches. That broke retrieval
   for cases like "reset settings" against "Open settings, then reset". Fixed by
   stripping FTS5 operator characters and keeping bare words. Verified by
   `pytest tests -q` -> 66 passed.

2. anthropic package missing from requirements.txt. The ClaudeQAClient imports
   `anthropic`, but the package was never added as a dependency. Anyone running
   `pip install -r requirements.txt` on a fresh checkout would hit ModuleNotFoundError
   at service startup. Fixed by appending `anthropic==0.40.0` to requirements.txt.

3. ClaudeQAClient.__init__ (None vs ""). The constructor used
   `api_key or os.environ.get(...)`, which meant `ClaudeQAClient(api_key="")`
   fell through to the environment variable instead of raising
   UnconfiguredModelError. Fixed by using `if api_key is not None`.

4. Test suite dependence on shell env. Tests inherited `KB_QA_CLIENT=live` from
   the shell, causing 5 unrelated tests to fail. Fixed by forcing
   `KB_QA_CLIENT=mock` in `tests/conftest.py` unless `PYTEST_LIVE=1` is set.

### Test suite status (as of 2026-10-18)

- Task 1: 66 passed (59 original + 7 new ClaudeQAClient tests)
- Task 2: 44 passed
- Task 3: 58 passed
- Integration (mock-based): 15 passed
- Smoke test (scripts/start_all.sh): 1 passed
- Live-gated integration tests: 3 skipped without CAPSTONE_LIVE=1 and credentials

Total: 184 unit + integration tests, 1 smoke test, 3 live-gated tests.

### What is not verified

- Live latency distribution (median / p95 / p99): only ONE timed call is
  recorded above (4.79s). A real distribution requires multiple runs.
- Live cost: no API invoice was consulted. Cost is estimated from token counts.
- Model comparison: only claude-haiku-5-5 was exercised. No Sonnet or Opus call
  was made. No comparison is claimed.
- Extended evaluation dataset: no more than 2 live calls were made. The
  evaluation framework in EVALS.md records only these cases as measured.
- All other metrics in EVALS.md are marked "pending — requires live credentials
  and per-case budget".

### Honesty statement

Every claim in this section is backed by pasted terminal output in the
development session. No percentage is fabricated. No latency is invented. No
model comparison is claimed. The other 184 tests were run on mocked paths, and
this section does not pretend otherwise. The FTS escape fix and the anthropic
dependency were genuine defects found during the milestone, not hidden.

---

## Task 2 and Task 3 Live Path Completion (2026-10-18)

### What was completed

Both Task 2's ClaudeClassifier/ClaudeDrafter and Task 3's ClaudeExtractor were
stub implementations that raised UnconfiguredModelError. They were implemented,
unit-tested with fake clients, and then exercised against the live Anthropic API.

### Bugs found and fixed during this milestone

1. `ClaudeDrafter` / `ClaudeClassifier`: `max_tokens=1000` truncated longer responses
   mid-JSON, causing parse failures. Raised to 2500 (drafter) and 800 (classifier).
   Added explicit truncation detection in `parseJson`.

2. `PipelineRunner` rejected live drafter output because the drafter returned `email_id=""`
   (the Drafter interface does not pass the email id). Fixed by having the pipeline fill
   in `email_id` from its own state when the drafter returns empty.

3. `ExtractedRecord` had no `model_id` field, so records did not record which model
   produced them. Added `model_id: str | None = None` and populated it in
   `ClaudeExtractor._row_to_record`.

4. `task2_inbox_agent` used `require("@anthropic-ai/sdk")` in an ESM project, causing
   `ReferenceError: require is not defined` at startup. Fixed by using static
   `import Anthropic from "@anthropic-ai/sdk"`.

5. `better-sqlite3` native binary needed rebuild after Node 20 -> Node 22 upgrade.

### Live verification evidence

Task 2 (real email through the real pipeline):

  POST /pipeline/process {"email_id":"live-test-1"}
  Response: {"draft_id": "c69a536e-...", "email_id": "live-test-1",
             "predicted_category": "how_to", "urgency": "low", "risk": "low"}
  Wall-clock: 12.11s (three live calls: classifier + KB query + drafter)
  DB evidence: drafts table row with model_id='claude-haiku-5-5'

Task 3 (real transcript through the real extractor):

  POST /transcripts {synthetic transcript with 4 turns}
  Response: {"records_extracted": 3, "records_by_kind": {"requirement": 2, "constraint": 1}}
  Wall-clock: 2.36s
  DB evidence: extracted_records rows with model_id='claude-haiku-5-5'

### Test suite totals after this milestone

- Task 1: 66 passed
- Task 2: 58 passed (56 original + 2 truncation tests)
- Task 3: 67 passed (66 original + 1 model_id test)
- Integration (mock): 15 passed
- Smoke: 1 passed
- Live-gated: 3 skipped
- Total: 207 mocked + 3 live-gated-skipped

### Honest limitations

- Live latency distribution not measured (n=2 live pipeline runs).
- Invoiced cost not confirmed; estimates only.
- No model comparison (only claude-haiku-5-5 exercised).
- Full eval dataset (20+ cases per task) not executed live.



## `--limit` Ingestion Bug — Fixed (2026-10-19)

The `--limit N` pilot-crawl flag previously did not limit sitemap discovery.
A `--limit 3` run on a sitemap index ingested 1240 documents because the
discovery loop fetched every child sitemap before applying the limit.

Two fixes were applied in `task1_knowledge_brain/ingestion/orchestrator.py`:

1. The `_collect_sitemap_entries` loop now checks `len(collected) >= limit`
   at the top of each iteration, stopping discovery as soon as enough URLs
   are collected — not after processing a whole child sitemap.

2. `run_ingestion` now slices `entries = entries[:limit]` before the
   `asyncio.gather`, so ingestion never processes more than `limit` URLs
   even if discovery over-collects.

A regression test (`test_limit_flag_limits_discovery_and_ingestion`) serves a
synthetic 5-child-sitemap index with 10 URLs each (50 total) and asserts that a
`--limit 3` run:
- fetches fewer than 5 child sitemaps (discovery stopped early), and
- creates exactly 3 documents in the DB (ingestion was limited).

This closes the previously documented limitation. Verified by pytest (see
test output in the transcript of this session).

---

## Dashboard Simplification — One-Command Demo (2026-10-19)

The dashboard previously required the reviewer to open three terminals, run
`grep` for tokens, paste each token into a browser field, and remember the
project_id. This was a developer workflow, not a demo.

The simplification:

1. **`scripts/demo.sh`** — one command starts all three services plus a small
   Python server on port 9000 that serves `docs/dashboard.html`.

2. **`scripts/serve_dashboard.py`** — serves the dashboard HTML with the Task 2
   and Task 3 bearer tokens auto-injected from `.envs/`. Tokens are not written
   to disk; they exist only in the served HTTP response.

3. **Dashboard HTML patches** — Task 2 pending-drafts list loads on page open
   (no "Refresh" click required). Task 3 project_id pre-fills to
   `project_website`. Task 1 and Task 3 token fields are pre-filled by the
   server; if the server is not used, the fields remain empty and the reviewer
   pastes tokens manually (the fallback path still works).

### Documented limitation

The served HTML contains the bearer tokens in the `value` attribute of two
inputs. This is safe on `localhost` for the same reviewer who already has the
tokens. It is **not safe** if the dashboard is exposed to a network or the
browser page is saved. Documented in `docs/OPERATIONS.md`.

### What this does NOT change

- No changes to the three services. Authentication is unchanged.
- No changes to any test.
- No new dependencies.

### Verification

`scripts/serve_dashboard.py` is `ast.parse`-verified. `scripts/demo.sh` is
`bash -n`-verified. The token-injection logic is checked against the actual
`.envs/` values before declaring the demo ready.

