"""3C schemas: change detection, change report, revised proposal."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ChangeKind = Literal["added", "removed", "modified", "unchanged", "unresolved"]
MatchStatus = Literal["confirmed", "ambiguous", "none"]
ApprovalStatus = Literal["pending_approval", "approved", "rejected"]


class BaselineRequirement(BaseModel):
    requirement_id: str
    description: str
    source_quote: str
    acceptance_criteria: list[str] = Field(default_factory=list)
    deadline: str | None = None


class BaselineSnapshot(BaseModel):
    project_id: str
    proposal_id: str
    version: int
    status: Literal["approved"]
    approved_by: str
    requirements: list[BaselineRequirement]
    estimate_totals: dict[str, float]
    deliverables: list[str] = Field(default_factory=list)
    exclusions: list[str] = Field(default_factory=list)
    captured_at: datetime


class FollowupRequirement(BaseModel):
    requirement_id: str
    description: str
    source_quote: str
    turn_id: str
    provenance: Literal["client_stated", "model_inferred"]
    tentative: bool = False


class RequirementMatch(BaseModel):
    baseline_requirement_id: str | None
    followup_requirement_id: str
    match_status: MatchStatus
    similarity: float = Field(ge=0.0, le=1.0)
    rationale: str


class DetectedChange(BaseModel):
    change_kind: ChangeKind
    baseline_requirement_id: str | None = None
    followup_requirement_id: str | None = None
    old_value: str | None = None
    proposed_new_value: str | None = None
    evidence: list[dict] = Field(default_factory=list)
    impact_effort_hours: float = Field(default=0.0, ge=0.0)
    unresolved_questions: list[str] = Field(default_factory=list)
    approval_status: ApprovalStatus = "pending_approval"
    out_of_scope: bool = False
    reviewer_confirmation_required: bool = False


class ChangeReport(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    report_id: str
    project_id: str
    baseline_proposal_id: str
    baseline_version: int
    followup_transcript_id: str
    created_at: datetime
    changes: list[DetectedChange]
    requirement_matches: list[RequirementMatch]
    totals_delta: dict[str, float]
    approved: bool = False
    approved_by: str | None = None
    approved_at: datetime | None = None
    model_id: str
    prompt_version: str


class RevisedProposalResult(BaseModel):
    report_id: str
    revised_proposal_id: str
    revised_version: int
    requires_approval_before_send: bool = True
    sent_simulated: bool = False
    sent_at: datetime | None = None
    sent_delivery_id: str | None = None
