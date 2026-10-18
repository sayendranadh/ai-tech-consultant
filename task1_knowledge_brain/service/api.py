"""Task 1 Knowledge Brain HTTP service.

Live-service note: vision and QA models are MOCKED. /health reports `degraded`.
"""
from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from ..ingestion.config import IngestionConfig
from ..qa.pipeline import QAPipeline
from ..retrieval.embedder import MockEmbedder
from ..retrieval.retriever import Retriever
from ..retrieval.vector_store import VectorStore
from ..retrieval.vision import MockVisionClient
from ..schemas.qa import QARequest
from .auth import Principal, require_admin, require_any_token
from .config import ServiceConfig
from .errors import http_exception_handler, validation_exception_handler
from .escalations import EscalationStore
from .jobs import JobStore
from .rate_limit import RateLimiter
from .ui_html import render_query_page
from .schemas import (
    EscalationCreateRequest,
    EscalationCreateResponse,
    EscalationResolveRequest,
    EscalationResolveResponse,
    HealthChecks,
    HealthResponse,
    IngestionRunRequest,
    IngestionRunResponse,
    IngestionStatusResponse,
    QueryRequest,
    QueryResponse,
)

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg: ServiceConfig = app.state.config
    ingestion_cfg: IngestionConfig = app.state.ingestion_cfg
    embedder = app.state.embedder
    retriever = Retriever(ingestion_cfg.db_path, embedder)
    VectorStore(ingestion_cfg.db_path, embedder.dim)
    app.state.retriever = retriever
    app.state.jobs = JobStore(ingestion_cfg.db_path)
    app.state.escalations = EscalationStore(ingestion_cfg.db_path)
    app.state.limiter = RateLimiter(cfg.rate_limit_per_minute)
    if app.state.qa_client is None:
        import os as _qa_os
        _qa_mode = _qa_os.environ.get("KB_QA_CLIENT", "mock").lower()
        if _qa_mode == "live":
            from ..qa.claude_client import ClaudeQAClient
            app.state.qa_client = ClaudeQAClient()
        else:
            app.state.qa_client = _MockQAClient()
    app.state.vision_client = app.state.vision_client or MockVisionClient()

    # 1D: recovery + optional scheduler
    import os
    from ..scheduler.recovery import recover_interrupted
    from ..scheduler.setup import build_scheduler
    recover_interrupted(ingestion_cfg)
    scheduler = None
    if os.environ.get("KB_SCHEDULER_ENABLED", "false").lower() == "true":
        cron_hour = int(os.environ.get("KB_INGESTION_CRON_HOUR", "2"))
        cron_minute = int(os.environ.get("KB_INGESTION_CRON_MINUTE", "0"))
        scheduler = build_scheduler(ingestion_cfg, cron_hour=cron_hour, cron_minute=cron_minute)
        scheduler.start()
        app.state.scheduler = scheduler
    yield
    if scheduler is not None:
        scheduler.shutdown(wait=False)


class _MockQAClient:
    model_id = "mock-qa/v1"
    is_live = False

    def answer(self, system: str, user: str) -> str:
        return "INSUFFICIENT"


def _default_embedder():
    """Real embeddings by default (matches what retrieval.index built)."""
    from ..retrieval.embedder import SentenceTransformerEmbedder
    return SentenceTransformerEmbedder()


def create_app(
    config: ServiceConfig | None = None,
    ingestion_cfg: IngestionConfig | None = None,
    embedder=None,
    qa_client=None,
    vision_client=None,
) -> FastAPI:
    config = config or ServiceConfig()
    ingestion_cfg = ingestion_cfg or IngestionConfig()
    app = FastAPI(title="AI Tech Consultant — Knowledge Brain", version="0.1.0", lifespan=lifespan)
    # Demo CORS: allows the static dashboard at docs/dashboard.html to call the API
    # from file:// (Origin: null). NOT acceptable for production. Restrict allow_origins
    # to the actual origin serving the dashboard when deployed.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from ..middleware.request_id import RequestIDMiddleware
    app.add_middleware(RequestIDMiddleware)

    app.state.config = config
    app.state.ingestion_cfg = ingestion_cfg
    app.state.embedder = embedder or _default_embedder()
    app.state.qa_client = qa_client
    app.state.vision_client = vision_client

    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)

    def _rate_limit(request: Request, principal: Principal = Depends(require_any_token)) -> Principal:
        if not request.app.state.limiter.allow(principal.token_id):
            raise HTTPException(status_code=429, detail="rate limit exceeded")
        return principal

    @app.get("/", response_class=None)
    def ui_home(request: Request):
        from fastapi.responses import HTMLResponse
        return HTMLResponse(render_query_page())

    @app.get("/kb")
    def ui_kb(request: Request):
        from fastapi.responses import HTMLResponse
        return HTMLResponse(render_query_page())

    @app.get("/health", response_model=HealthResponse)
    def health(request: Request) -> HealthResponse:
        db_ok = True
        try:
            with request.app.state.jobs._conn() as con:
                con.execute("SELECT 1").fetchone()
        except Exception:
            db_ok = False
        qa_live = getattr(request.app.state.qa_client, "is_live", False)
        vision_live = getattr(request.app.state.vision_client, "is_live", False)
        checks = HealthChecks(
            db="ok" if db_ok else "fail",
            embedding_provider="ok",
            vision_model="ok" if vision_live else "mocked",
            qa_model="ok" if qa_live else "mocked",
        )
        if not db_ok:
            return JSONResponse(status_code=503, content=HealthResponse(status="unavailable", checks=checks).model_dump())
        degraded = (not qa_live) or (not vision_live)
        return HealthResponse(status="degraded" if degraded else "ok", checks=checks)

    @app.post("/query", response_model=QueryResponse)
    def query(
        body: QueryRequest,
        request: Request,
        principal: Principal = Depends(_rate_limit),
    ) -> QueryResponse:
        import os as _os
        if _os.environ.get('KB_QA_CLIENT', 'mock') == 'live':
            from ..qa.claude_client import ClaudeQAClient
            if isinstance(request.app.state.qa_client, ClaudeQAClient):
                result = request.app.state.retriever.search(body.question, top_k=10, mode='hybrid')
                chunks = [c for c in result.chunks if c.score >= 0.15]
                chunk_dicts = [
                    {'chunk_id': c.chunk_id, 'url': c.url, 'section_heading': c.section_heading, 'text': c.text, 'title': None}
                    for c in chunks
                ]
                resp = request.app.state.qa_client.structured_answer(body.question, chunk_dicts)
                return QueryResponse(**resp.model_dump())
        if _os.environ.get('KB_QA_CLIENT', 'mock') == 'fixture':
            from ..qa.fixture_client import FixtureQAClient
            from pathlib import Path as _Path
            _fix = FixtureQAClient(_Path(__file__).parent.parent.parent / 'data' / 'qa_fixtures' / 'qa_fixture_answers.json')
            _resp = _fix.structured_answer(body.question)
            if _resp is not None:
                return QueryResponse(**_resp.model_dump())
        pipeline = QAPipeline(retriever=request.app.state.retriever, client=request.app.state.qa_client)
        resp = pipeline.run(QARequest(question=body.question))
        return QueryResponse(**resp.model_dump())

    @app.post("/ingestion/run", response_model=IngestionRunResponse, status_code=status.HTTP_202_ACCEPTED)
    def ingestion_run(
        body: IngestionRunRequest,
        request: Request,
        principal: Principal = Depends(require_admin),
    ):
        source = request.app.state.ingestion_cfg.source_domain
        active = request.app.state.jobs.active_run(source)
        if active:
            return JSONResponse(
                status_code=200,
                content=IngestionRunResponse(
                    run_id=active["run_id"], status="already_running", message="ingestion already in progress",
                ).model_dump(),
            )
        run = request.app.state.jobs.create(source, requested_by=principal.token_id)
        return IngestionRunResponse(run_id=run["run_id"], status="queued", message="ingestion job queued")

    @app.get("/ingestion/status", response_model=IngestionStatusResponse)
    def ingestion_status(
        request: Request,
        principal: Principal = Depends(_rate_limit),
    ) -> IngestionStatusResponse:
        source = request.app.state.ingestion_cfg.source_domain
        row = request.app.state.jobs.latest(source)
        if row is None:
            return IngestionStatusResponse(run_id=None, status="idle")
        counts = json.loads(row["counts_json"]) if row.get("counts_json") else {}
        errors = json.loads(row["errors_json"]) if row.get("errors_json") else []
        return IngestionStatusResponse(
            run_id=row["run_id"], status=row["status"], source=row["source"],
            requested_at=row["requested_at"], started_at=row.get("started_at"),
            finished_at=row.get("finished_at"), counts=counts, errors=errors,
        )

    @app.post("/escalations", response_model=EscalationCreateResponse, status_code=status.HTTP_201_CREATED)
    def create_escalation(
        body: EscalationCreateRequest,
        request: Request,
        principal: Principal = Depends(_rate_limit),
    ) -> EscalationCreateResponse:
        row = request.app.state.escalations.create(
            question=body.question, reason=body.reason,
            related_chunk_ids=body.related_chunk_ids, created_by=principal.token_id,
        )
        return EscalationCreateResponse(id=row["id"], status=row["status"], created_at=row["created_at"])

    @app.post("/escalations/{escalation_id}/resolve", response_model=EscalationResolveResponse)
    def resolve_escalation(
        escalation_id: str,
        body: EscalationResolveRequest,
        request: Request,
        principal: Principal = Depends(require_admin),
    ) -> EscalationResolveResponse:
        try:
            row = request.app.state.escalations.resolve(
                escalation_id,
                expert_answer=body.expert_answer,
                approved_for_general=body.approved_for_general_knowledge,
                approved_for_customer=body.approved_for_customer_specific,
                approver=principal.token_id,
                embedder=request.app.state.embedder,  # enables synchronous promotion
            )
        except KeyError:
            raise HTTPException(status_code=404, detail="escalation not found")
        return EscalationResolveResponse(
            escalation_id=escalation_id, version=row["version"],
            approved_for_general_knowledge=bool(row["approved_for_general_knowledge"]),
            approved_for_customer_specific=bool(row["approved_for_customer_specific"]),
            approved_by=row["approved_by"], approved_at=row["approved_at"],
            promotion_run_id=row["promotion_run_id"],
            promotion_error=row.get("promotion_error"),
        )

    return app
