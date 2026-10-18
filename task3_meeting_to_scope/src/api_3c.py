"""3C HTTP endpoints."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .baseline import load_baseline
from .change_detector import detect_changes
from .change_report_md import render_markdown
from .change_report_service import ApprovalRejected, ChangeReportService, SendRejected
from .persistence.db_3c import DAO3C
from .rebaseliner import build_revised_proposal, totals_delta
from .schemas_3c import ChangeReport, FollowupRequirement


class ApproveBody(BaseModel):
    approved_by: str


def build_router_3c(
    dao_3c: DAO3C,
    service: ChangeReportService,
    baseline_path: Path,
    followup_path: Path,
) -> APIRouter:
    r = APIRouter()

    @r.post("/projects/{project_id}/followup/{transcript_id}/compare")
    def compare(project_id: str, transcript_id: str):
        try:
            baseline = load_baseline(project_id, baseline_path)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"no approved baseline for {project_id}")

        raw = json.loads(followup_path.read_text(encoding="utf-8"))
        if raw.get("project_id") != project_id or raw.get("transcript_id") != transcript_id:
            raise HTTPException(status_code=404, detail=f"no follow-up extraction for {project_id}/{transcript_id}")

        reqs = [FollowupRequirement.model_validate(x) for x in raw["extracted_requirements"]]
        matches, changes = detect_changes(
            baseline, reqs, list(raw.get("decisions", [])), list(raw.get("commitments", []))
        )

        report = ChangeReport(
            report_id=f"cr-{uuid.uuid4()}",
            project_id=project_id,
            baseline_proposal_id=baseline.proposal_id,
            baseline_version=baseline.version,
            followup_transcript_id=transcript_id,
            created_at=datetime.now(timezone.utc),
            changes=changes,
            requirement_matches=matches,
            totals_delta={},
            approved=False,
            approved_by=None,
            approved_at=None,
            model_id="rebaseliner/deterministic-v1",
            prompt_version="v1",
        )

        revised = build_revised_proposal(baseline, report)
        report.totals_delta = totals_delta(baseline, revised)

        dao_3c.insert_change_report(report.model_dump())
        dao_3c.insert_revised_proposal(report.report_id, project_id, revised.model_dump())

        return {
            "report": report.model_dump(mode="json"),
            "markdown": render_markdown(report),
            "revised_proposal": revised.model_dump(mode="json"),
        }

    @r.post("/change-reports/{report_id}/approve")
    def approve(report_id: str, body: ApproveBody):
        try:
            data = service.approve(report_id, body.approved_by)
        except KeyError:
            raise HTTPException(status_code=404, detail="report not found")
        except ApprovalRejected as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        return data

    @r.post("/change-reports/{report_id}/send")
    def send(report_id: str):
        try:
            delivery_id = service.send_simulated(report_id)
        except SendRejected as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        return {
            "delivery_id": delivery_id,
            "mode": "simulated",
            "is_simulated": True,
            "delivery_status": "simulated_sent",
        }

    return r
