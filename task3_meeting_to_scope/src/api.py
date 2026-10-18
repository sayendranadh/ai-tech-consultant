"""Task 3 HTTP service (3A + 3B + 3C routes)."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from .config import Task3Config
from .extractor.mock import MockExtractor
from .ingestion.chunker import chunk_transcript
from .persistence.db import DAO
from .schemas import (
    Conflict,
    IngestTranscriptRequest,
    IngestTranscriptResponse,
    OpenQuestion,
    ProjectExtraction,
    ProjectViewResponse,
    Requirement,
)

log = logging.getLogger(__name__)


def _default_extractor() -> MockExtractor:
    return MockExtractor(Path(__file__).parent.parent / "data" / "mock_extractions.json")


def get_dao(request: Request) -> DAO:
    return request.app.state.dao


def require_token(request: Request) -> None:
    cfg: Task3Config = request.app.state.config
    if not cfg.api_token:
        return
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer ") or auth[7:].strip() != cfg.api_token:
        raise HTTPException(status_code=401, detail="invalid or missing bearer token")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    cfg: Task3Config = app.state.config
    if not getattr(app.state, "dao", None):
        app.state.dao = DAO(cfg.db_path)
    if not getattr(app.state, "extractor", None):
        app.state.extractor = _default_extractor()
    import os as _os
    if _os.environ.get("ANTHROPIC_API_KEY") and _os.environ.get("CLAUDE_EXTRACTOR_MODEL"):
        from .extractor.claude import ClaudeExtractor
        app.state.extractor = ClaudeExtractor(
            api_key=_os.environ["ANTHROPIC_API_KEY"],
            model_id=_os.environ["CLAUDE_EXTRACTOR_MODEL"],
            prompt_version=_os.environ.get("CLAUDE_PROMPT_VERSION", "v1"),
        )
    yield


def create_app(config: Task3Config | None = None) -> FastAPI:
    cfg = config or Task3Config()
    app = FastAPI(title="AI Tech Consultant — Meeting to Scope", version="0.1.0", lifespan=lifespan)
    # Demo CORS: allows the static dashboard at docs/dashboard.html to call the API
    # from file:// (Origin: null). NOT acceptable for production.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from .middleware.request_id import RequestIDMiddleware
    app.add_middleware(RequestIDMiddleware)

    app.state.config = cfg

    # Synchronous defaults (so routes work without lifespan)
    app.state.dao = DAO(cfg.db_path)
    app.state.extractor = _default_extractor()

    @app.exception_handler(HTTPException)
    async def _http_handler(request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.status_code, "message": exc.detail, "details": None}},
        )

    @app.get("/health")
    def health(request: Request) -> dict:
        return {"status": "ok", "extractor": type(request.app.state.extractor).__name__}

    @app.post("/transcripts", response_model=IngestTranscriptResponse, status_code=status.HTTP_201_CREATED)
    def ingest_transcript(
        body: IngestTranscriptRequest,
        request: Request,
        _: None = Depends(require_token),
        dao: DAO = Depends(get_dao),
    ) -> IngestTranscriptResponse:
        t = body.transcript
        dao.insert_transcript(t.model_dump(mode="json"))
        chunks = chunk_transcript(
            t,
            max_chars=request.app.state.config.chunk_max_chars,
            overlap_chars=request.app.state.config.chunk_overlap_chars,
        )
        all_records = []
        for chunk in chunks:
            all_records.extend(request.app.state.extractor.extract(chunk))
        dao.insert_extracted_records(t.project_id, t.transcript_id, [r.model_dump(mode="json") for r in all_records])
        by_kind: dict[str, int] = {}
        for r in all_records:
            by_kind[r.record_kind] = by_kind.get(r.record_kind, 0) + 1
        return IngestTranscriptResponse(
            transcript_id=t.transcript_id,
            records_extracted=len(all_records),
            records_by_kind=by_kind,
        )

    @app.get("/projects/{project_id}", response_model=ProjectViewResponse)
    def project_view(project_id: str, request: Request, _: None = Depends(require_token)) -> ProjectViewResponse:
        dao: DAO = request.app.state.dao
        reqs = [Requirement.model_validate(r) for r in dao.latest_requirements_for_project(project_id)]
        oqs = [OpenQuestion.model_validate(q) for q in dao.open_questions_for_project(project_id)]
        cfs = [Conflict.model_validate(c) for c in dao.conflicts_for_project(project_id)]
        return ProjectViewResponse(
            project=ProjectExtraction(project_id=project_id, requirements=reqs, open_questions=oqs, conflicts=cfs)
        )

    # ---- 3B routes ----
    from .api_3b import build_router
    from .feasibility_agent import FeasibilityAgent
    from .persistence.db_3b import DAO3B
    from .proposal_service import ProposalService
    from .workflow_3b import Workflow3B

    fixtures_dir = Path(__file__).parent.parent / "tests" / "fixtures"
    dao_3b = DAO3B(cfg.db_path)

    import os as _os
    _kb_base = _os.environ.get('KB_BASE_URL', '').strip()
    if _kb_base:
        from .kb_client import HTTPKBClient
        _kb = HTTPKBClient(base_url=_kb_base, bearer_token=_os.environ.get('KB_BEARER_TOKEN', '').strip())
        feasibility = FeasibilityAgent(kb=_kb, model_id='feasibility/http-v1')
    else:
        class _UnavailableKB:
            def query(self, question: str) -> dict:
                return {"status": "unavailable", "answer": "", "sources": [], "escalation_required": True}
        feasibility = FeasibilityAgent(kb=_UnavailableKB(), model_id='feasibility/no-kb-v1')
    workflow = Workflow3B(
        dao_3a=app.state.dao,
        dao_3b=dao_3b,
        feasibility=feasibility,
        estimate_fixture_path=fixtures_dir / "estimate_fixtures.json",
        proposal_fixture_path=fixtures_dir / "proposal_fixtures.json",
    )
    proposal_service = ProposalService(dao_3b)
    app.include_router(build_router(dao_3b, workflow, proposal_service))

    # ---- 3C routes ----
    from .api_3c import build_router_3c
    from .change_report_service import ChangeReportService
    from .persistence.db_3c import DAO3C

    dao_3c = DAO3C(cfg.db_path)
    change_service = ChangeReportService(dao_3c)
    app.include_router(build_router_3c(
        dao_3c,
        change_service,
        baseline_path=fixtures_dir / "baseline_fixtures.json",
        followup_path=fixtures_dir / "followup_changes_fixtures.json",
    ))

    return app


def run() -> None:
    import uvicorn
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(create_app(), host="127.0.0.1", port=8200)
