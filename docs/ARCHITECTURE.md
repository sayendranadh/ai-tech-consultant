# AI Tech Consultant — Architecture

## Services

- **Task 1: Knowledge Brain** — Python FastAPI on `:8000`. Ingestion, retrieval, `/query`, `/escalations`, `/health`.
- **Task 2: Inbox Agent** — TypeScript Fastify on `:8100`. Classifies emails, calls Task 1 `/query`, generates drafts, review UI, consecutive-approval tracking.
- **Task 3: Meeting-to-Scope** — Python FastAPI on `:8200`. Transcript ingestion, requirement extraction, Task 1 `/query` for feasibility, estimates / proposals / change reports, approval gate, simulated delivery.

## Diagram

```mermaid
graph LR
    U[Reviewer]
    U -->|GET /review, POST /review/:id/action| T2[Task 2 Inbox Agent<br/>TypeScript Fastify :8100]
    T2 -->|POST /query, POST /escalations| T1[Task 1 Knowledge Brain<br/>Python FastAPI :8000]
    U -->|POST /projects/:pid/followup/:tid/compare<br/>POST /change-reports/:id/approve/send| T3[Task 3 Meeting-to-Scope<br/>Python FastAPI :8200]
    T3 -->|POST /query| T1
    T1 -.defines.- CT[docs/api/knowledge_brain.openapi.json]
    T2 -.uses.- CT
    T3 -.uses.- CT
Contract
Single source of truth: docs/api/knowledge_brain.openapi.json (exported from Task 1).

Task 2's typed KB client is generated from this contract via openapi-typescript.

Task 3's hand-written HTTP client mirrors the contract; drift is caught by integration tests against a live Task 1 process.

Isolation
Tasks 2 and 3 do NOT import Task 1's Python modules. They interact exclusively via HTTP.

Each task has its own SQLite file: data/knowledge_brain.sqlite3, data/task2.sqlite3, data/task3.sqlite3.

No shared knowledge store. Knowledge updates flow from Task 1 to Tasks 2/3 via HTTP on each request.

Failure behavior
Task 1 unreachable → Task 2 KBClient raises KBUnavailableError → PipelineRunner forces insufficient_evidence=true and escalation_required=true. No fabricated answer.

Task 1 unreachable → Task 3 FeasibilityAgent returns needs_clarification with status unverified. No fabricated feasibility conclusion.

Delivery
Tasks 2 and 3 use simulated delivery adapters only. Every delivery record is is_simulated: true.

No real customer emails or client proposals are sent in the current capstone state.

Honest boundaries
Live Claude is not exercised unless ANTHROPIC_API_KEY and model IDs are set.

No live crawl of the support center has been performed.

Fixture-driven verification (Task 1 KB_QA_CLIENT=fixture) is labeled [FIXTURE].

Integration test results distinguish mock-integration (real HTTP between services, mocked model clients) from live tests (gated by CAPSTONE_LIVE=1).
