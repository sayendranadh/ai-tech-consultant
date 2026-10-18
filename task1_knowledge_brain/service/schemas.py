"""Request/response models for the Task 1 HTTP surface."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..schemas.qa import ImageRef, QAResponse, SourceRef


class QueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(..., min_length=1, max_length=2000)


class QueryResponse(QAResponse):
    pass


class IngestionRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["full", "pilot"] = "pilot"
    pilot_limit: int = Field(default=3, ge=1, le=100)


class IngestionRunResponse(BaseModel):
    run_id: str
    status: Literal["queued", "already_running"]
    message: str


class IngestionStatusResponse(BaseModel):
    run_id: str | None
    status: Literal["idle", "queued", "running", "succeeded", "failed", "partial"]
    source: str | None = None
    requested_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    counts: dict[str, int] = Field(default_factory=dict)
    errors: list[dict] = Field(default_factory=list)


class EscalationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(..., min_length=1, max_length=2000)
    reason: str = Field(..., min_length=1, max_length=2000)
    related_chunk_ids: list[int] = Field(default_factory=list, max_length=50)


class EscalationCreateResponse(BaseModel):
    id: str
    status: Literal["open", "in_review", "resolved", "closed"]
    created_at: str


class EscalationResolveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expert_answer: str = Field(..., min_length=1, max_length=8000)
    approved_for_general_knowledge: bool = False
    approved_for_customer_specific: bool = False


class EscalationResolveResponse(BaseModel):
    escalation_id: str
    version: int
    approved_for_general_knowledge: bool
    approved_for_customer_specific: bool
    approved_by: str
    approved_at: str
    promotion_run_id: str | None = None
    promotion_error: str | None = None


class HealthChecks(BaseModel):
    db: Literal["ok", "fail"]
    embedding_provider: Literal["ok", "fail"]
    vision_model: Literal["ok", "mocked", "fail", "unconfigured"]
    qa_model: Literal["ok", "mocked", "fail", "unconfigured"]


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded", "unavailable"]
    checks: HealthChecks

