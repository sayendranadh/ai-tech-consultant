import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.baseline import load_baseline
from src.change_detector import detect_changes
from src.change_report_service import ApprovalRejected, ChangeReportService, SendRejected
from src.persistence.db_3c import DAO3C
from src.rebaseliner import build_revised_proposal, totals_delta
from src.schemas_3c import ChangeReport, FollowupRequirement

FIX = Path(__file__).parent / "fixtures"


def _setup(tmp_path):
    dao = DAO3C(tmp_path / "t3c.sqlite3")
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
    dao.insert_change_report(report.model_dump())
    dao.insert_revised_proposal(report.report_id, "project_website", revised.model_dump())
    return dao, report.report_id


def test_send_before_approve_rejected(tmp_path):
    dao, rid = _setup(tmp_path)
    with pytest.raises(SendRejected):
        ChangeReportService(dao).send_simulated(rid)


def test_approve_then_send_succeeds(tmp_path):
    dao, rid = _setup(tmp_path)
    svc = ChangeReportService(dao)
    svc.approve(rid, approved_by="alice.manager@example.com")
    delivery_id = svc.send_simulated(rid)
    assert delivery_id


def test_unknown_report_approve_raises(tmp_path):
    dao = DAO3C(tmp_path / "t3c.sqlite3")
    with pytest.raises(KeyError):
        ChangeReportService(dao).approve("cr-nope", approved_by="alice")


def test_unknown_report_send_raises(tmp_path):
    dao = DAO3C(tmp_path / "t3c.sqlite3")
    with pytest.raises(SendRejected):
        ChangeReportService(dao).send_simulated("cr-nope")


def test_approve_without_revised_proposal_rejected(tmp_path):
    dao = DAO3C(tmp_path / "t3c.sqlite3")
    report = ChangeReport(
        report_id="cr-fake", project_id="project_website",
        baseline_proposal_id="prop-1", baseline_version=1,
        followup_transcript_id="meeting_3_followup",
        created_at=datetime.now(timezone.utc),
        changes=[], requirement_matches=[], totals_delta={},
        approved=False, approved_by=None, approved_at=None,
        model_id="x", prompt_version="v1",
    )
    dao.insert_change_report(report.model_dump())
    with pytest.raises(ApprovalRejected):
        ChangeReportService(dao).approve("cr-fake", approved_by="alice")
