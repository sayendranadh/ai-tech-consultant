"""Unit tests for run_evals.py criteria evaluation (pure logic, no HTTP)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

import pytest

import run_evals as runner


def test_task1_answered_criteria_pass():
    actual = {"status": "answered", "sources": [{"url": "u", "chunk_id": 1}], "answer": "Use CSV."}
    c = {"expected_status": "answered", "min_sources": 1, "required_keywords_in_answer": ["csv"]}
    assert runner._task1_criteria_pass(actual, c) is True


def test_task1_abstain_criteria_pass():
    actual = {"status": "insufficient_evidence", "sources": [], "answer": "Not enough."}
    assert runner._task1_criteria_pass(actual, {"expected_status": "insufficient_evidence", "must_abstain": True}) is True


def test_task1_fails_if_wrong_status():
    actual = {"status": "answered", "sources": [{"url": "u", "chunk_id": 1}], "answer": "x"}
    assert runner._task1_criteria_pass(actual, {"expected_status": "insufficient_evidence"}) is False


def test_task1_fails_if_missing_keyword():
    actual = {"status": "answered", "sources": [{"url": "u", "chunk_id": 1}], "answer": "refund"}
    c = {"expected_status": "answered", "required_keywords_in_answer": ["csv"]}
    assert runner._task1_criteria_pass(actual, c) is False


def test_unauthorized_commitment_detected():
    assert runner._detect_unauthorized_commitment("We will refund your full amount by Friday.") is True


def test_unauthorized_commitment_clean():
    assert runner._detect_unauthorized_commitment("I have routed this to our billing team.") is False


def test_task2_category_match_pass():
    actual = {"draft": {"category": "how_to", "urgency": "normal", "risk": "low"}}
    c = {"expected_category": "how_to", "expected_urgency_in": ["normal", "low"]}
    ok, _ = runner._task2_criteria_pass(actual, c)
    assert ok is True


def test_task2_category_mismatch_fail():
    actual = {"draft": {"category": "refund_cancellation", "urgency": "high", "risk": "high"}}
    c = {"expected_category": "how_to"}
    ok, reason = runner._task2_criteria_pass(actual, c)
    assert ok is False
    assert "category" in reason


def test_task2_unauthorized_commitment_fail():
    actual = {"draft": {"draft_reply": "We will refund your full amount by Friday.", "insufficient_evidence": 0}}
    c = {"must_not_contain_unauthorized_commitment": True}
    ok, reason = runner._task2_criteria_pass(actual, c)
    assert ok is False
    assert "commitment" in reason


def test_task3_min_requirements_pass():
    actual = {"ingest": {"records_by_kind": {"requirement": 3}}}
    ok, _ = runner._task3_criteria_pass(actual, {"min_requirements_extracted": 2}, [], [], [], [])
    assert ok is True


def test_task3_min_requirements_fail():
    actual = {"ingest": {"records_by_kind": {"requirement": 1}}}
    ok, reason = runner._task3_criteria_pass(actual, {"min_requirements_extracted": 2}, [], [], [], [])
    assert ok is False
    assert "requirements" in reason


