"""Pydantic v2 models for Task 3A.

Rules encoded here:
- Every Requirement carries source_refs pointing at specific transcript turns.
- Missing info becomes an OpenQuestion, never an invented Requirement.
- Every Requirement distinguishes client_stated vs model_inferred.
- Requirement versioning is monotonic; created_version and updated_version track history.
"""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field
from pydantic import ConfigDict


ConfirmationStatus = Literal["confirmed", "unclear", "disputed"]
Priority = Literal["low", "medium", "high", "critical"]
CapabilityStatus = Literal["unknown", "available", "partial", "missing", "not_checked"]
EstimateStatus = Literal["not_estimated", "rough", "detailed", "approved"]
Provenance = Literal["client_stated", "model_inferred"]
RecordKind = Literal["decision", "requirement", "constraint", "dependency", "commitment", "open_question"]


class TranscriptTurn(BaseModel):
    turn_id: str = Field(..., min_length=1)
    speaker: str = Field(..., min_length=1)
    timestamp: str | None = None
    text: str = Field(..., min_length=1)


class Transcript(BaseModel):
    transcript_id: str
    meeting_number: int
    project_id: str
    meeting_date: date
    participants: list[str]
    is_synthetic: bool = True
    turns: list[TranscriptTurn]


class TurnRef(BaseModel):
    transcript_id: str
    turn_id: str
    speaker: str
    timestamp: str | None = None
    quote: str = Field(..., min_length=1, max_length=500)


class ExtractedRecord(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    record_kind: RecordKind
    text: str = Field(..., min_length=1)
    source_refs: list[TurnRef] = Field(..., min_length=1)
    provenance: Provenance
    confidence: Literal["low", "medium", "high"] = "medium"
    model_id: str | None = None


class Requirement(BaseModel):
    requirement_id: str
    project_id: str
    description: str = Field(..., min_length=1)
    source_meeting: int
    source_refs: list[TurnRef] = Field(..., min_length=1)
    confirmation_status: ConfirmationStatus = "unclear"
    priority: Priority = "medium"
    existing_product_capability: CapabilityStatus = "unknown"
    acceptance_criteria: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    estimate_status: EstimateStatus = "not_estimated"
    provenance: Provenance
    version: int = 1
    created_version: int = 1
    updated_version: int = 1
    status: Literal["active", "superseded", "removed"] = "active"
    superseded_by: str | None = None
    notes: str | None = None


class OpenQuestion(BaseModel):
    question_id: str
    project_id: str
    text: str = Field(..., min_length=1)
    raised_by: str | None = None
    source_refs: list[TurnRef] = Field(..., min_length=1)
    status: Literal["open", "resolved"] = "open"


class Conflict(BaseModel):
    conflict_id: str
    project_id: str
    kind: Literal["contradiction", "unresolved"]
    involved_requirement_ids: list[str] = Field(default_factory=list)
    text: str
    source_refs: list[TurnRef] = Field(..., min_length=1)
    resolution: Literal["unresolved", "resolved_by_later_meeting"] = "unresolved"


class ProjectExtraction(BaseModel):
    project_id: str
    requirements: list[Requirement]
    open_questions: list[OpenQuestion]
    decisions: list[ExtractedRecord] = Field(default_factory=list)
    constraints: list[ExtractedRecord] = Field(default_factory=list)
    dependencies: list[ExtractedRecord] = Field(default_factory=list)
    commitments: list[ExtractedRecord] = Field(default_factory=list)
    conflicts: list[Conflict] = Field(default_factory=list)


class IngestTranscriptRequest(BaseModel):
    transcript: Transcript


class IngestTranscriptResponse(BaseModel):
    transcript_id: str
    records_extracted: int
    records_by_kind: dict[str, int]


class ProjectViewResponse(BaseModel):
    project: ProjectExtraction
