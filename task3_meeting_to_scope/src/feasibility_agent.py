"""Feasibility agent for 3B. Calls Task 1 POST /query per requirement; classifies result.

The requirement_id is embedded in the question string so a live Task 1 (or a
test mock keyed on the requirement ID) can attribute the query to the requirement.

Classification rules (encoded, not LLM-decided):
- insufficient_evidence or empty sources -> needs_clarification + status escalated
- kb failure / unavailable -> needs_clarification + status unverified
- kb answered with "not support" / "no native" -> potential_custom_development
- kb answered with "limitation" / "partial" -> existing_feature_with_limitation
- kb answered otherwise -> existing_configuration
The classification 'unsupported' does NOT exist by design.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Protocol

from .schemas import Requirement
from .schemas_3b import FeasibilityCheck, FeasibilityClass

log = logging.getLogger(__name__)


class KBQueryClient(Protocol):
    def query(self, question: str) -> dict: ...


def _classify_from_kb(kb_status: str, kb_answer: str, sources: list) -> tuple[FeasibilityClass, str]:
    if kb_status == "insufficient_evidence" or not sources:
        return "needs_clarification", "escalated"
    if kb_status != "answered":
        return "needs_clarification", "unverified"
    a = kb_answer.lower()
    if any(t in a for t in ("not support", "no native", "not available", "would require custom")):
        return "potential_custom_development", "checked"
    if any(t in a for t in ("limitation", "partial", "only single")):
        return "existing_feature_with_limitation", "checked"
    return "existing_configuration", "checked"


class FeasibilityAgent:
    def __init__(self, kb: KBQueryClient, model_id: str = "feasibility/heuristic-v1", prompt_version: str = "v1") -> None:
        self._kb = kb
        self._model_id = model_id
        self._prompt_version = prompt_version

    def check(self, requirement: Requirement) -> FeasibilityCheck:
        question = (
            f"[{requirement.requirement_id}] "
            "Does the product support the following requirement? "
            f"{requirement.description}"
        )
        try:
            kb = self._kb.query(question)
        except Exception as exc:
            log.warning("kb query failed: %s", exc)
            return FeasibilityCheck(
                requirement_id=requirement.requirement_id,
                project_id=requirement.project_id,
                classification="needs_clarification",
                status="unverified",
                evidence_chunk_ids=[],
                kb_status="unavailable",
                notes=f"kb unavailable: {exc}",
                model_id=self._model_id,
                prompt_version=self._prompt_version,
                checked_at=datetime.now(timezone.utc),
            )

        kb_status = kb.get("status", "unavailable")
        kb_answer = kb.get("answer", "") or ""
        sources = kb.get("sources") or []
        chunk_ids = [int(s["chunk_id"]) for s in sources if isinstance(s, dict) and "chunk_id" in s]

        classification, status = _classify_from_kb(kb_status, kb_answer, sources)

        return FeasibilityCheck(
            requirement_id=requirement.requirement_id,
            project_id=requirement.project_id,
            classification=classification,
            status=status,
            evidence_chunk_ids=chunk_ids,
            kb_status=kb_status if kb_status in ("answered", "insufficient_evidence", "failed", "unavailable") else "unavailable",
            notes=f"kb_answer_length={len(kb_answer)}",
            model_id=self._model_id,
            prompt_version=self._prompt_version,
            checked_at=datetime.now(timezone.utc),
        )
