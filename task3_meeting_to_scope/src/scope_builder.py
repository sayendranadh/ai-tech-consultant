"""Build ScopeDocument from merged requirements + proposal fixture."""
from __future__ import annotations

import json
from pathlib import Path

from .schemas import Requirement
from .schemas_3b import ScopeDocument


def build_scope(project_id: str, requirements: list[Requirement], fixture_path: Path) -> ScopeDocument:
    fix = json.loads(fixture_path.read_text(encoding="utf-8")).get(project_id, {})
    return ScopeDocument(
        project_id=project_id,
        objective=f"Project {project_id}: deliver the agreed requirements from the source transcripts.",
        current_problem="See source transcripts for the client's stated problem.",
        agreed_requirement_ids=[r.requirement_id for r in requirements],
        proposed_solution="Deliver each agreed requirement per the transcript evidence.",
        deliverables=[r.description for r in requirements],
        exclusions=list(fix.get("exclusions", [])),
        assumptions=list(fix.get("client_responsibilities", [])),
        dependencies=[],
        acceptance_criteria_by_req={r.requirement_id: [] for r in requirements},
        client_responsibilities=list(fix.get("client_responsibilities", [])),
        open_questions=[],
        risks=list(fix.get("risks", [])),
    )
