"""3B schemas: feasibility, estimates, scope, proposal, approval."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


FeasibilityClass = Literal[
    "existing_configuration",
    "existing_feature_with_limitation",
    "potential_custom_development",
    "needs_clarification",
]
FeasibilityStatus = Literal["checked", "unverified", "escalated"]
EstimateTaskKind = Literal[
    "requirements_clarification", "technical_design",
    "backend_implementation", "frontend_implementation",
    "integration", "testing", "deployment", "documentation",
]
EstimateReviewerStatus = Literal["provisional_unreviewed", "reviewed_approved", "rejected"]
ProposalStatus = Literal["draft", "revised", "approved", "sent_simulated"]


class FeasibilityCheck(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    requirement_id: str
    project_id: str
    classification: FeasibilityClass
    status: FeasibilityStatus
    evidence_chunk_ids: list[int] = Field(default_factory=list)
    kb_status: Literal["answered", "insufficient_evidence", "failed", "unavailable"]
    notes: str = ""
    model_id: str
    prompt_version: str
    checked_at: datetime


class EstimateTask(BaseModel):
    task_id: str
    requirement_id: str
    task: EstimateTaskKind
    low_hours: float = Field(ge=0)
    likely_hours: float = Field(ge=0)
    high_hours: float = Field(ge=0)
    rationale: str
    assumptions: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    uncertainty: Literal["low", "medium", "high"] = "medium"
    reviewer_status: EstimateReviewerStatus = "provisional_unreviewed"


class EstimateTotals(BaseModel):
    low_hours: float
    likely_hours: float
    high_hours: float
    by_task: dict[str, dict[str, float]]
    by_requirement: dict[str, dict[str, float]]


class ScopeDocument(BaseModel):
    project_id: str
    objective: str
    current_problem: str
    agreed_requirement_ids: list[str]
    proposed_solution: str
    deliverables: list[str]
    exclusions: list[str]
    assumptions: list[str]
    dependencies: list[str]
    acceptance_criteria_by_req: dict[str, list[str]]
    client_responsibilities: list[str]
    open_questions: list[str]
    risks: list[str]


class PricingAssumptions(BaseModel):
    hourly_rate: float | None = None
    currency: str | None = None
    taxes_included: bool | None = None
    total_price: float | None = None
    unresolved: list[str] = Field(
        default_factory=lambda: ["hourly_rate", "currency", "taxes_included", "total_price"]
    )


class ProposalVersion(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    proposal_id: str
    project_id: str
    version: int
    status: ProposalStatus
    created_at: datetime
    executive_summary: str
    client_problem: str
    solution: str
    scope: ScopeDocument
    timeline_assumptions: list[str]
    estimate_totals: EstimateTotals
    pricing_assumptions: PricingAssumptions
    exclusions: list[str]
    dependencies: list[str]
    risks: list[str]
    open_questions: list[str]
    next_steps: str
    model_id: str
    prompt_version: str
    generated_by: str
    text_hash: str


class ProposalApproval(BaseModel):
    proposal_id: str
    version: int
    approved_by: str
    approved_at: datetime
    approval_text_hash: str
    reason: str | None = None
