# Design — AI Tech Consultant, Task 1 Knowledge Brain

## State
- **Repo:** greenfield, empty at start.
- **Milestone:** 1A (ingestion pipeline).
- **Tests:** see `REPORT.md` at repo root — updated only with actual command output.

## Architecture (current)
Task 1 only. Tasks 2/3 are out of scope for this milestone.

    ┌──────────────────────────────────────────────────────────┐
    │ Task 1 — Knowledge Brain (Python, FastAPI in milestone C)│
    │                                                          │
    │  sitemap_parser → fetcher → parser → manifest/storage    │
    │         (1A)         (1A)    (1A)       (1A)             │
    │                                                          │
    │  chunker → embedder → retriever → qa_pipeline            │
    │          (1B)         (1B)        (1B)                   │
    │                                                          │
    │  FastAPI endpoints (1C)  ·  APScheduler daily (1D)       │
    └──────────────────────────────────────────────────────────┘

## ADRs

### ADR-001 — FastAPI for Task 1 HTTP layer
Repo is greenfield; no existing framework to preserve. FastAPI chosen for
Pydantic v2 integration and OpenAPI generation. Applied in 1C.

### ADR-002 — SQLite (WAL) for persistence
Single-file, zero-server, adequate for capstone scale. WAL enables
concurrent readers during ingestion writes. Path: `KB_DB_PATH`.

### ADR-003 — Trafilatura + BeautifulSoup for HTML
Trafilatura for main-body extraction (benchmarked well for precision).
BeautifulSoup + lxml for structured metadata (h1–h6 hierarchy, image src,
canonical link) that Trafilatura does not expose cleanly.

### ADR-004 — Recursive sitemap-index support
Brilliant Directories publishes a sitemap INDEX per official docs, not a
flat urlset. Parser must recurse. Guard against index cycles.

### ADR-005 — sentence-transformers (all-MiniLM-L6-v2) for embeddings
Offline, reproducible, no API key. Anthropic has no embeddings endpoint.
Applied in 1B.

### ADR-006 — sqlite-vec for vector search
Keeps the store in the same SQLite file as the manifest. Applied in 1B.

### ADR-007 — Claude vision for image descriptions
Model ID recorded verbatim in `data/model_record.json` at first real use.
**MOCKED** until ANTHROPIC_API_KEY and model ID are provided. Labeled
SIMULATED in storage. Applied in 1B.

### ADR-008 — Claude for QA generation
Same as ADR-007. **MOCKED** until credentials provided. Applied in 1B.

### ADR-009 — APScheduler + SQLAlchemyJobStore
In-process with FastAPI. Job functions must be module-level (picklable).
Applied in 1D.

### ADR-010 — Bearer token auth
Single env var `KB_API_TOKEN`. Task 2 and Task 3 each receive distinct
tokens in a later milestone so calls can be attributed. Applied in 1C.

### ADR-011 — Change detection: lastmod-first, hash-fallback
If sitemap lastmod exists and matches manifest → skip. Otherwise fetch,
SHA-256 body hash; unchanged hash → skip. Applied in 1A.

### ADR-012 — Failure classification
Transient (429, 5xx, timeout, connection reset) retried with exponential
backoff up to `KB_MAX_RETRIES`. Permanent (404, 410, parse failure,
robots-disallow) not retried; recorded as `failed_permanent`. Applied in 1A.

### ADR-013 — Removed pages: deactivate now, purge after grace
Chunks deactivated immediately (`is_active=0`). Manifest row kept with
`status=removed`, `removed_at`. Purge job (future) may hard-delete after
`KB_REMOVED_GRACE_DAYS` (default 30). Applied in 1A (deactivation) and 1D
(purge).

### ADR-014 — No confidence field in /query
The B prompt permits `confidence` only if calibrated and evaluated. No
calibration plan is committed, so the field is omitted. Applied in 1B/1C.

### ADR-015 — Retrieval architecture: chunk_embeddings table + FTS5
Embeddings stored as raw float32 BLOBs in SQLite. FTS5 provides keyword search.
Hybrid ranking normalizes each source to [0,1] and combines with configurable weights.

### ADR-016 — sqlite-vec as optimization, in-memory cosine as baseline
Tests run regardless of whether sqlite-vec loads. When unavailable, the store logs
"VECTOR SEARCH FALLBACK" and uses in-memory cosine. This is documented in the
capability report; it is a scale limitation, not a correctness issue at capstone size.

### ADR-017 — Vision + QA models are MOCKED in 1B
No live Anthropic call is made in the delivered tests. Every stored description
carries status `simulated` and `model_id="mock-vision/v1"`. QA outputs are
labeled by `MockQAClient`. Capability report marks both as "requires live verification".

### ADR-018 — Retrieval score semantics: cosine in [-1, 1]
`VectorStore.search` returns cosine similarity in the mathematical range [-1, 1].
Hybrid normalization in `Retriever` remaps each source to [0,1] before weighting,
so the *hybrid* combined score is in [0,1]. Any `min_top_score` threshold must be
written against the *specific* mode's range. The default `QAPipeline.min_top_score`
of 0.15 is a heuristic cosine floor and is **not yet calibrated against real data** —
noted for the eval run once a live model is available.

### ADR-019 — FTS5 rebuild at VectorStore bootstrap
`VectorStore._bootstrap` runs `INSERT INTO chunks_fts(chunks_fts) VALUES('rebuild')`
after applying the retrieval schema. This indexes any chunks that existed before FTS
triggers were created (e.g., a 1A DB upgraded to 1B, or test seeding order). Rebuild
is idempotent and FTS5-native. This is why keyword search works even when chunks were
inserted before the trigger existed.

### ADR-020 — VectorStore ensures base schema
`VectorStore` constructs a `ManifestStore` in `_bootstrap` before applying the
retrieval schema, so tests and production code can construct `VectorStore` directly
against a fresh DB without a prior ingestion run.

### ADR-021 — Per-role bearer tokens and approval gate
Three env-var tokens: `KB_API_TOKEN_TASK2`, `KB_API_TOKEN_TASK3`, `KB_API_TOKEN_ADMIN`.
`/escalations/{id}/resolve` requires `admin`. `expert_id` is derived from the token role,
not user input, so the approval record is auditable.

### ADR-022 — Escalation promotion is queued
Resolved-and-approved-for-general-knowledge answers are queued as a follow-up ingestion
job in 1D. In 1C the resolution stores `promotion_run_id=None`; 1D will populate it when
the promoted synthetic document is ingested. Customer-specific answers are never promoted.

### ADR-025 — Error envelope wired (1C.1)
HTTPException → `{"error": {"code", "message", "details"}}`. RequestValidationError →
same envelope with details=[{loc, type, msg}]. Consumers (Tasks 2, 3) rely on this shape.

### ADR-026 — Promotion runs as a dedicated job (1D)
Approved escalations promote immediately (not batched with daily cron).
`promote_escalation` ingests the synthetic document through the same pipeline:
write_document → chunk → write_chunks → deactivate_stale → mark_processed → embed.
Idempotent on content hash.

### ADR-027 — Single-run lock via SQLite BEGIN IMMEDIATE
`run_daily_ingestion` acquires a database-level write lock (BEGIN IMMEDIATE, timeout=0)
before starting. Concurrent runs fail fast and record a `lock_held` error in
ingestion_runs. APScheduler additionally sets `max_instances=1` on the job.

### ADR-028 — Scheduler off by default
`KB_SCHEDULER_ENABLED=false` by default. Tests never enable it. To run in production,
set it true and confirm the behavior via `/ingestion/status`.
### ADR-023 — Health status semantics
200 for `ok` and `degraded`; 503 for `unavailable` only. `degraded` reflects mocked or
unconfigured model providers. The service can still answer with honest
`insufficient_evidence`/`failed` responses. Clients should inspect `status` in the body.

### ADR-024 — Rate limit and timeout defaults
10 rpm per token (in-memory token bucket). `/query` end-to-end 30s. `/ingestion/run` returns
in ≤2s with a job pointer — the actual run is asynchronous. Pydantic `extra="forbid"` on all
request bodies.

### ADR-030 — Task 2: Fastify + TypeScript + better-sqlite3
Task 2 is an agent, not a UI. Fastify chosen for typed routes and low overhead.
Persistence is a sibling SQLite file (`T2_DB_PATH`), separate from Task 1's DB.
This guarantees Task 2 does not read/write Task 1's knowledge tables directly;
all knowledge access is via HTTP.

### ADR-031 — Task 1 client: codegen from OpenAPI
`openapi-typescript` generates `task2_inbox_agent/src/kb/openapi.d.ts` from
`docs/api/knowledge_brain.openapi.json`. Any Task 1 schema change requires
re-export + regeneration; drift becomes a compile-time error, not a runtime bug.

### ADR-032 — Mock classifier/drafter in 2A; live classes present but unexercised
Tests use `MockClassifier` / `MockDrafter` keyed by exact (subject, body) fixtures.
`ClaudeClassifier` / `ClaudeDrafter` constructors raise `UnconfiguredModelError`
if `ANTHROPIC_API_KEY` or model IDs are absent. Capability report flags both as
"requires live verification" until a real call is executed and logged.

### ADR-033 — Idempotency key = sha256(email_id + pipeline_version)
Re-running the pipeline for the same email and same pipeline version returns the
existing draft_id. A prompt or model change should bump `pipeline_version`
(currently `CLAUDE_PROMPT_VERSION`) so re-processing produces a new draft, not a
silent overwrite. This is the mechanism that will make the 20-consecutive rule in
2B correct: it counts *distinct* drafts on *distinct* pipeline versions, never the
same draft twice.

### ADR-034 — Non-fabrication on KB failure
If `KBClient.query` raises, `PipelineRunner` forces `insufficient_evidence=true`
and `escalation_required=true` regardless of what the drafter returned. This
prevents a mock or live drafter from inventing a product answer when the
knowledge service is unavailable. Verified by `pipeline_insufficient_evidence.test.ts`.

### ADR-035 — Task 2 review UI: server-rendered HTML, no SPA
Review interface is server-rendered HTML + form posts. No React, no Next.js.
Routes: GET /review, GET /review/:id, POST /review/:id/action.
Renders: original email, classification, draft, sources, warnings, model/prompt
version, review history, per-category counter. Every page carries a
"Simulated delivery only" notice.

### ADR-036 — Simulated delivery adapter
`SimulatedDeliveryAdapter` returns `delivery_status: "simulated_sent"` (NOT `"delivered"`).
`is_simulated: true` is stored on every delivery row. UI shows "Simulated send".
A `FailingDeliveryAdapter` exists for tests only; never constructed in the server.
The delivery adapter protocol is stable so an SMTP adapter can replace the simulated
one later without touching the review service or the state machine.

### ADR-037 — Comparison policy for "substantive changes"
Normalization: trim, collapse whitespace, lowercase, strip signature block
(default separators: "\n-- \n", "\n—\n"). If normalized texts are equal, the draft
qualifies as "unchanged". Otherwise disqualified with a reason. Documented in
`src/autonomy/compare.ts`. Any future change to normalization is a behavior change
that MUST be recorded in this ADR and re-verified by `compare.test.ts`.

### ADR-038 — 20-consecutive rule semantics
- Counter is per category (7 categories). Subcategory support deferred.
- Threshold 20. At 20 → `eligible_for_autonomy: true` on the counter row only.
- Eligibility does NOT trigger any autonomous sending. No auto-send code path exists.
- Enable endpoint (`POST /admin/autonomy/:category/enable`) sets the flag and logs
  an autonomy_event. Disable endpoint logs a kill-switch event.
- Reset on: edit, reject, escalate, delivery failure, duplicate event.
- High-risk exclusion list defaults to `refund_cancellation, complaint`.
  These categories can accumulate counts but NEVER become eligible.
- Every qualifying and disqualifying event is stored in `qualifying_events` with
  timestamps and reason. Every enable/disable is in `autonomy_events` with actor
  and reason. Full audit trail.

### ADR-039 — Feedback loop: versioned prompts, not retraining
Corrections are persisted with reason. `repeatedCorrections()` query surfaces the
top-N (category, reason) pairs so a human can propose a prompt or template version
bump. `CLAUDE_PROMPT_VERSION` in `.env` is the version identifier. No auto-retraining.
Any observed "improvement" from a prompt change MUST be demonstrated by 2C's
evaluation against the frozen dataset, not assumed.

### ADR-040 — Scope of exactOptionalPropertyTypes exception
`tsconfig.json` retains `"exactOptionalPropertyTypes": true` for all code.
For caller-controlled optional fields in a small number of interfaces — `Dao.insertApproval`,
`QualifyingInput`, `ReviewDecisionInput` — the optional fields are declared as
`?: string | undefined` (rather than `?: string`) so that callers may pass `undefined`
explicitly without producing a type error. This exception is scoped to interfaces where
the "absence" is a natural part of the domain (no correction reason, no edited text,
no disqualifying reason) and does not silently mask real type errors. All other code
remains under the strict flag.

### ADR-041 — Specific disqualifying reason overrides generic
`recordQualifyingEvent` prefers the caller-supplied `disqualifying_reason` when
present. Only when the caller does not supply one does the state machine fall back
to its generic reason (`delivery_not_successful`, `draft_edited`). This produces
more specific audit-trail entries and matches the specific reasons emitted by
`ReviewService` (`delivery_failed`, `edited_by_reviewer`, `rejected`, `escalated`).


## Model Identifiers (recorded 2026-10-18)

All five model slots use `claude-haiku-5-5`, chosen for cost control:

- KB_QA_MODEL=claude-haiku-5-5
- KB_VISION_MODEL=claude-haiku-5-5
- CLAUDE_CLASSIFIER_MODEL=claude-haiku-5-5
- CLAUDE_DRAFTER_MODEL=claude-haiku-5-5
- CLAUDE_EXTRACTOR_MODEL=claude-haiku-5-5

Provider: Anthropic direct API
Pricing at record time (from Anthropic docs):
- Haiku 5.5: $0.10 input / $0.50 output per MTok (up to 100K prompt tokens)

Constraint: API balance is $5.00. Sonnet 5.5 ($2/$10 per MTok) is not affordable
for a full evaluation run. Haiku 5.5 was selected to stay within budget.
This is a budget constraint, not a quality recommendation.

First live call verified 2026-10-18:
- /v1/messages, model=claude-haiku-5-5, HTTP 200, stop_reason=end_turn
- usage: input_tokens=11, output_tokens=14 (cost ~ $0.0000081)
