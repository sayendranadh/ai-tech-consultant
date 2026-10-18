import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from src.baseline import load_baseline
from src.change_detector import detect_changes
from src.rebaseliner import build_revised_proposal, totals_delta
from src.schemas_3c import ChangeReport, FollowupRequirement

FIX = Path(__file__).parent / "fixtures"


def _build():
    baseline = load_baseline("project_website", FIX / "baseline_fixtures.json")
    raw = json.loads((FIX / "followup_changes_fixtures.json").read_text(encoding="utf-8"))
    reqs = [FollowupRequirement.model_validate(r) for r in raw["extracted_requirements"]]
    matches, changes = detect_changes(baseline, reqs, raw["decisions"], raw["commitments"])
    report = ChangeReport(
        report_id=f"cr-{uuid.uuid4()}",
        project_id="project_website",
        baseline_proposal_id=baseline.proposal_id,
        baseline_version=baseline.version,
        followup_transcript_id="meeting_3_followup",
        created_at=datetime.now(timezone.utc),
        changes=changes, requirement_matches=matches, totals_delta={},
        approved=False, approved_by=None, approved_at=None,
        model_id="rebaseliner/deterministic-v1", prompt_version="v1",
    )
    revised = build_revised_proposal(baseline, report)
    report.totals_delta = totals_delta(baseline, revised)
    return baseline, report, revised


def test_baseline_version_not_bumped_by_comparison():
    baseline, _, _ = _build()
    assert baseline.version == 1


def test_revised_is_n_plus_1_and_status_revised():
    baseline, _, revised = _build()
    assert revised.version == baseline.version + 1
    assert revised.status == "revised"


def test_totals_delta_keys():
    baseline, _, revised = _build()
    d = totals_delta(baseline, revised)
    assert set(d.keys()) == {"low_hours_delta", "likely_hours_delta", "high_hours_delta"}


def test_revised_totals_at_least_baseline():
    baseline, _, revised = _build()
    old_low = baseline.estimate_totals.get("low_hours", 0.0)
    assert revised.estimate_totals.low_hours >= old_low
