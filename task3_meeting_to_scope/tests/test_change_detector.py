import json
from pathlib import Path

import pytest

from src.baseline import load_baseline
from src.change_detector import detect_changes
from src.schemas_3c import FollowupRequirement

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture
def parsed():
    baseline = load_baseline("project_website", FIX / "baseline_fixtures.json")
    raw = json.loads((FIX / "followup_changes_fixtures.json").read_text(encoding="utf-8"))
    reqs = [FollowupRequirement.model_validate(r) for r in raw["extracted_requirements"]]
    return baseline, reqs, list(raw["decisions"]), list(raw["commitments"])


def test_all_change_kinds_present(parsed):
    baseline, reqs, decisions, commitments = parsed
    _, changes = detect_changes(baseline, reqs, decisions, commitments)
    kinds = {c.change_kind for c in changes}
    assert "added" in kinds
    assert "removed" in kinds
    assert "modified" in kinds
    assert "unchanged" in kinds or "modified" in kinds
    assert "unresolved" in kinds


def test_out_of_scope_mobile_app_flagged(parsed):
    baseline, reqs, decisions, commitments = parsed
    _, changes = detect_changes(baseline, reqs, decisions, commitments)
    oos = [c for c in changes if c.out_of_scope]
    assert len(oos) >= 1
    assert any("mobile" in (c.proposed_new_value or "").lower() for c in oos)


def test_deadline_change_detected(parsed):
    baseline, reqs, decisions, commitments = parsed
    _, changes = detect_changes(baseline, reqs, decisions, commitments)
    deadline = [c for c in changes if c.change_kind == "modified" and "deadline=" in (c.proposed_new_value or "")]
    assert len(deadline) == 1
    assert "2025-04-01" in deadline[0].proposed_new_value
    assert "2025-03-15" in deadline[0].old_value


def test_contact_form_destination_change_detected(parsed):
    baseline, reqs, decisions, commitments = parsed
    _, changes = detect_changes(baseline, reqs, decisions, commitments)
    mods = [
        c for c in changes
        if c.change_kind == "modified"
        and c.old_value and "sales" in c.old_value.lower()
        and c.proposed_new_value and "support" in c.proposed_new_value.lower()
    ]
    assert mods, "expected sales -> support modification"


def test_newsletter_addition_detected(parsed):
    baseline, reqs, decisions, commitments = parsed
    _, changes = detect_changes(baseline, reqs, decisions, commitments)
    added = [c for c in changes if c.change_kind == "added" and not c.out_of_scope]
    assert any("newsletter" in (c.proposed_new_value or "").lower() for c in added)


def test_blog_removal_decision_detected(parsed):
    baseline, reqs, decisions, commitments = parsed
    _, changes = detect_changes(baseline, reqs, decisions, commitments)
    removed = [c for c in changes if c.change_kind == "removed"]
    blog_hits = [
        c for c in removed
        if "blog" in (c.old_value or "").lower()
        or (c.evidence and any("blog" in (ev.get("quote") or "").lower() for ev in c.evidence))
    ]
    assert blog_hits, "expected a 'removed' change for the blog"


def test_ambiguous_requirement_marked_unresolved(parsed):
    baseline, reqs, decisions, commitments = parsed
    _, changes = detect_changes(baseline, reqs, decisions, commitments)
    unresolved = [c for c in changes if c.change_kind == "unresolved"]
    assert len(unresolved) >= 1
    assert all(c.reviewer_confirmation_required for c in unresolved)
