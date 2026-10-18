"""Deterministic proposal writer. No invented prices; no live model call."""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .schemas import Requirement
from .schemas_3b import EstimateTotals, PricingAssumptions, ProposalVersion, ScopeDocument


def _canonical_text(p: ProposalVersion) -> str:
    fields = [
        p.executive_summary, p.client_problem, p.solution,
        p.next_steps, "|".join(p.exclusions), "|".join(p.dependencies),
        "|".join(p.risks), "|".join(p.open_questions),
    ]
    return "|".join(fields)


def _hash(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


class ProposalWriter:
    def __init__(self, fixture_path: Path, model_id: str = "proposal/deterministic-v1", prompt_version: str = "v1") -> None:
        self._fixtures = json.loads(fixture_path.read_text(encoding="utf-8"))
        self._model_id = model_id
        self._prompt_version = prompt_version

    def write(
        self,
        project_id: str,
        requirements: list[Requirement],
        scope: ScopeDocument,
        totals: EstimateTotals,
        generated_by: str,
    ) -> ProposalVersion:
        fix = self._fixtures.get(project_id, {})
        exec_summary = fix.get("executive_summary_template", "Proposal for {project_id}").format(
            project_id=project_id, requirement_count=len(requirements)
        )
        next_steps = fix.get("next_steps_template", "Await client response.")

        draft = ProposalVersion(
            proposal_id=str(uuid.uuid4()),
            project_id=project_id,
            version=1,
            status="draft",
            created_at=datetime.now(timezone.utc),
            executive_summary=exec_summary,
            client_problem=scope.current_problem,
            solution=scope.proposed_solution,
            scope=scope,
            timeline_assumptions=["Dependent on timely delivery of client responsibilities"],
            estimate_totals=totals,
            pricing_assumptions=PricingAssumptions(),
            exclusions=list(fix.get("exclusions", [])),
            dependencies=[],
            risks=list(fix.get("risks", [])),
            open_questions=list(scope.open_questions),
            next_steps=next_steps,
            model_id=self._model_id,
            prompt_version=self._prompt_version,
            generated_by=generated_by,
            text_hash="",
        )
        draft.text_hash = _hash(_canonical_text(draft))
        return draft
