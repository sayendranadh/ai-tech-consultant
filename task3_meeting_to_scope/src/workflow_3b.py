"""End-to-end 3B workflow."""
from __future__ import annotations

from pathlib import Path

from .estimator import aggregate, build_tasks_from_fixtures
from .feasibility_agent import FeasibilityAgent
from .persistence.db import DAO
from .persistence.db_3b import DAO3B
from .proposal_writer import ProposalWriter
from .schemas import Requirement
from .scope_builder import build_scope


class Workflow3B:
    def __init__(
        self,
        dao_3a: DAO,
        dao_3b: DAO3B,
        feasibility: FeasibilityAgent,
        estimate_fixture_path: Path,
        proposal_fixture_path: Path,
    ) -> None:
        self._dao_3a = dao_3a
        self._dao_3b = dao_3b
        self._feasibility = feasibility
        self._estimate_fixture_path = estimate_fixture_path
        self._proposal_fixture_path = proposal_fixture_path
        self._writer = ProposalWriter(proposal_fixture_path)

    def run(self, project_id: str, generated_by: str = "system"):
        raw = self._dao_3a.latest_requirements_for_project(project_id)
        requirements = [Requirement.model_validate(r) for r in raw]

        checks = [self._feasibility.check(r) for r in requirements]
        for c in checks:
            self._dao_3b.insert_feasibility_check(project_id, c.model_dump())

        tasks = build_tasks_from_fixtures([r.requirement_id for r in requirements], self._estimate_fixture_path)
        for t in tasks:
            self._dao_3b.insert_estimate_task(project_id, t.model_dump())
        totals = aggregate(tasks)

        scope = build_scope(project_id, requirements, self._proposal_fixture_path)
        proposal = self._writer.write(project_id, requirements, scope, totals, generated_by=generated_by)
        self._dao_3b.insert_proposal(proposal.model_dump())
        return {"feasibility": checks, "tasks": tasks, "totals": totals, "scope": scope, "proposal": proposal}
