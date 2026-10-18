"""Pydantic v2 models for the QA contract. No confidence field (ADR-014)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AnswerStatus = Literal["answered", "insufficient_evidence", "failed"]


class SourceRef(BaseModel):
    title: str | None = None
    url: str
    section: str | None = None
    chunk_id: int


class ImageRef(BaseModel):
    # `model_id` names the vision model; suppress Pydantic's protected namespace check.
    model_config = ConfigDict(protected_namespaces=())

    src: str
    description: str | None = None
    model_id: str | None = None
    status: Literal["ok", "ambiguous", "failed", "simulated"]


class QARequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


class QAResponse(BaseModel):
    question: str
    status: AnswerStatus
    answer: str = ""
    sources: list[SourceRef] = Field(default_factory=list)
    image_refs: list[ImageRef] = Field(default_factory=list)
    escalation_required: bool = False
