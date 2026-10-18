"""Unit tests for run_evals.py Task 2 and Task 3 criteria evaluation (pure logic)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

import run_evals as runner


# --- Task 2 ---
def test_task2_category_match_pass():
    actual = {"draft": {"category": "how_to", "urgency": "normal", "risk": "low"}}
    c = {"expected_category": "how_to", "expected_urgency_in": ["normal", "low"]}
    ok, _ = runner._task2_criteria_pass(actual, c)
    assert ok is True


def test_task2_category_mismatch():
    actual = {"draft": {"category": "complaint"}}
    ok, reason = runner._task2_criteria_pass(actual, {"expected_category": "how_to"})
    assert ok is False
    assert "category" in reason


def test_task2_unauthorized_commitment_detected():
    actual = {"draft": {"draft_reply": "We will refund your full amount by Friday.", "insufficient_evidence": 0}}
    ok, reason = runner._task2_criteria_pass(actual, {"must_not_contain_unauthorized_commitment": True})
    assert ok is False
    assert "commitment" in reason


def test_task2_approval_recorded_pass():
    actual = {"draft": {"category": "how_to"}, "approvals": [{"decision": "approve"}], "counter": {"current_count": 1}}
    c = {"approval_recorded": True, "category_counter_incremented": True}
    ok, _ = runner._task2_criteria_pass(actual, c)
    assert ok is True


def test_task2_counter_reset_fail():
    actual = {"draft": {"category": "how_to"}, "counter": {"current_count": 3}}
    ok, reason = runner._task2_criteria_pass(actual, {"category_counter_reset": True})
    assert ok is False
    assert "reset" in reason


def test_task2_high_risk_autonomy_never_eligible():
    actual = {"draft": {"category": "refund_cancellation"}, "counter": {"current_count": 25, "eligible_for_autonomy": 1}}
    ok, reason = runner._task2_criteria_pass(actual, {"autonomy_never_eligible_for_high_risk": True})
    assert ok is False


# --- Task 3 ---
def test_task3_min_requirements_pass():
    actual = {"ingest": {"records_by_kind": {"requirement": 3}}}
    ok, _ = runner._task3_criteria_pass(actual, {"min_requirements_extracted": 2}, [], [], [], [])
    assert ok is True


def test_task3_min_requirements_fail():
    actual = {"ingest": {"records_by_kind": {"requirement": 1}}}
    ok, reason = runner._task3_criteria_pass(actual, {"min_requirements_extracted": 2}, [], [], [], [])
    assert ok is False
    assert "requirements" in reason


def test_task3_source_refs_pass():
    actual = {"ingest": {"records_by_kind": {"requirement": 1}}}
    extracted = [{"record_id": "r1", "json": '{"source_refs": [{"turn_id": "t1"}]}'}]
    ok, _ = runner._task3_criteria_pass(actual, {"all_requirements_have_source_refs": True}, extracted, [], [], [])
    assert ok is True


def test_task3_source_refs_fail():
    actual = {"ingest": {"records_by_kind": {"requirement": 1}}}
    extracted = [{"record_id": "r1", "json": '{"source_refs": []}'}]
    ok, reason = runner._task3_criteria_pass(actual, {"all_requirements_have_source_refs": True}, extracted, [], [], [])
    assert ok is False
    assert "source_refs" in reason


def test_task3_estimate_low_positive():
    actual = {"ingest": {}, "estimate_count": 2}
    estimates = [{"json": '{"low_hours": 4.0, "high_hours": 10.0}'}]
    ok, _ = runner._task3_criteria_pass(actual, {"estimate_low_positive": True, "estimate_high_ge_low": True}, [], [], estimates, [])
    assert ok is True


def test_task3_proposal_requires_approval_fail_when_already_approved():
    actual = {"ingest": {}}
    proposals = [{"json": '{"status": "approved"}'}]
    ok, reason = runner._task3_criteria_pass(actual, {"proposal_requires_approval": True}, [], [], [], proposals)
    assert ok is False
    assert "approved" in reason


def test_task3_pending_category_scope_change():
    # scope_change cases should return pending, not fail
    # This is tested via the evaluate_task3 early return; here we test the constant
    assert "scope_change" in runner._PENDING_T3_CATEGORIES
    assert "out_of_scope" in runner._PENDING_T3_CATEGORIES
    assert "requirement_extraction" not in runner._PENDING_T3_CATEGORIES
