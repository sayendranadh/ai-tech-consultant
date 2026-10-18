from pathlib import Path

import pytest

from src.estimator import aggregate, build_tasks_from_fixtures
from src.persistence.db_3b import DAO3B
from src.proposal_service import ProposalService, SendRejected
from src.proposal_writer import ProposalWriter
from src.schemas import Requirement, TurnRef
from src.scope_builder import build_scope

FIXTURES = Path(__file__).parent / "fixtures"


def _req(rid: str, description: str = "homepage redesign") -> Requirement:
    return Requirement(
        requirement_id=rid, project_id="project_website", description=description,
        source_meeting=1,
        source_refs=[TurnRef(transcript_id="t", turn_id="turn-001", speaker="s", quote="q")],
        provenance="client_stated",
    )


def _make(dao: DAO3B):
    reqs = [_req("REQ-meeting_1_website-001")]
    tasks = build_tasks_from_fixtures(["REQ-meeting_1_website-001"], FIXTURES / "estimate_fixtures.json")
    totals = aggregate(tasks)
    scope = build_scope("project_website", reqs, FIXTURES / "proposal_fixtures.json")
    writer = ProposalWriter(FIXTURES / "proposal_fixtures.json")
    proposal = writer.write("project_website", reqs, scope, totals, generated_by="test")
    dao.insert_proposal(proposal.model_dump())
    return proposal


def test_send_before_approve_rejected(tmp_path):
    dao = DAO3B(tmp_path / "t3b.sqlite3")
    p = _make(dao)
    with pytest.raises(SendRejected):
        ProposalService(dao).send_simulated(p.proposal_id)


def test_approve_then_send(tmp_path):
    dao = DAO3B(tmp_path / "t3b.sqlite3")
    p = _make(dao)
    svc = ProposalService(dao)
    approval = svc.approve(p.proposal_id, p.version, approved_by="admin@x")
    assert approval.approval_text_hash
    delivery_id = svc.send_simulated(p.proposal_id)
    assert delivery_id


def test_pricing_is_unresolved_by_default(tmp_path):
    dao = DAO3B(tmp_path / "t3b.sqlite3")
    p = _make(dao)
    assert p.pricing_assumptions.hourly_rate is None
    assert p.pricing_assumptions.currency is None
    assert p.pricing_assumptions.total_price is None
    assert "hourly_rate" in p.pricing_assumptions.unresolved
    assert "currency" in p.pricing_assumptions.unresolved


def test_proposal_contains_required_sections(tmp_path):
    dao = DAO3B(tmp_path / "t3b.sqlite3")
    p = _make(dao)
    assert p.executive_summary
    assert p.client_problem
    assert p.solution
    assert p.next_steps
    assert p.estimate_totals.high_hours >= 0
    assert p.scope.agreed_requirement_ids == ["REQ-meeting_1_website-001"]
