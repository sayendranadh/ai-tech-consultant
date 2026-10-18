import json
from pathlib import Path

import pytest

from src.feasibility_agent import FeasibilityAgent
from src.schemas import Requirement, TurnRef

FIX = Path(__file__).parent / "fixtures" / "feasibility_fixtures.json"


class _MockKB:
    def __init__(self, fixtures: dict) -> None:
        self._fix = fixtures

    def query(self, question: str) -> dict:
        for rid, row in self._fix.items():
            if rid in question:
                return {
                    "status": row["kb_status"],
                    "answer": row["kb_answer"],
                    "sources": row["kb_sources"],
                    "escalation_required": row["escalation_required"],
                }
        return {"status": "insufficient_evidence", "answer": "", "sources": [], "escalation_required": True}


def _req(rid: str, description: str) -> Requirement:
    return Requirement(
        requirement_id=rid, project_id="project_website", description=description,
        source_meeting=1,
        source_refs=[TurnRef(transcript_id="t", turn_id="turn-001", speaker="s", quote="q")],
        confirmation_status="confirmed", priority="medium",
        existing_product_capability="not_checked", provenance="client_stated",
    )


@pytest.fixture
def fixtures():
    return json.loads(FIX.read_text(encoding="utf-8"))


def test_existing_configuration(fixtures):
    agent = FeasibilityAgent(_MockKB(fixtures))
    check = agent.check(_req("REQ-meeting_1_website-001", "homepage redesign"))
    assert check.classification == "existing_configuration"
    assert check.status == "checked"
    assert check.evidence_chunk_ids


def test_insufficient_evidence_becomes_needs_clarification(fixtures):
    agent = FeasibilityAgent(_MockKB(fixtures))
    check = agent.check(_req("REQ-meeting_3_followup-002", "newsletter signup"))
    assert check.classification == "needs_clarification"
    assert check.status == "escalated"
    assert check.kb_status == "insufficient_evidence"


def test_kb_unavailable_marks_unverified():
    class _Broken:
        def query(self, q: str) -> dict:
            raise RuntimeError("kb down")
    agent = FeasibilityAgent(_Broken())
    check = agent.check(_req("REQ-any", "anything"))
    assert check.classification == "needs_clarification"
    assert check.status == "unverified"
    assert check.kb_status == "unavailable"


def test_no_unsupported_classification_in_schema():
    import typing
    from src.schemas_3b import FeasibilityClass  # noqa: PLC0415
    args = typing.get_args(FeasibilityClass)
    assert "unsupported" not in args
