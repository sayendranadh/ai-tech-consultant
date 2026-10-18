"""Verification C with LIVE Claude QA in Task 1.

Task 3's FeasibilityAgent classifies a live Claude answer from live Task 1.
Requires CAPSTONE_LIVE=1, ANTHROPIC_API_KEY, CLAUDE_QA_MODEL.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from .conftest import write_evidence


ROOT = Path(__file__).parent.parent


def test_live_c_task3_feasibility_on_live_answer(live_gate, live_task1):
    sys.path.insert(0, str(ROOT / "task3_meeting_to_scope"))
    from src.feasibility_agent import FeasibilityAgent
    from src.kb_client import HTTPKBClient
    from src.schemas import Requirement, TurnRef

    kb = HTTPKBClient(
        base_url=live_task1["base_url"],
        bearer_token="t3-token",
        timeout_ms=60000,
        max_retries=1,
    )
    agent = FeasibilityAgent(kb=kb)
    req = Requirement(
        requirement_id="REQ-LIVE-C", project_id="project_live",
        description="reset a password",
        source_meeting=1,
        source_refs=[TurnRef(transcript_id="t", turn_id="turn-001", speaker="s", quote="q")],
        provenance="client_stated",
    )
    check = agent.check(req)
    evidence = write_evidence("live_c_feasibility", {
        "check": check.model_dump(mode="json"),
        "task1_log": live_task1["log_path"],
    })
    if check.kb_status == "insufficient_evidence":
        pytest.skip(
            f"live Task 1 returned insufficient_evidence; feasibility cannot be classified. "
            f"Evidence: {evidence}"
        )
    assert check.classification in (
        "existing_configuration",
        "existing_feature_with_limitation",
        "potential_custom_development",
        "needs_clarification",
    ), check
    assert check.status in ("checked", "unverified", "escalated"), check
