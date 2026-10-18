"""Deterministic revised proposal builder. Unchanged work preserved; modified work re-estimated."""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

from .schemas_3b import EstimateTotals, PricingAssumptions, ProposalVersion, ScopeDocument
from .schemas_3c import BaselineSnapshot, ChangeReport, RevisedProposalResult


def _hash(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def build_revised_proposal(baseline: BaselineSnapshot, report: ChangeReport) -> ProposalVersion:
    affected_hours = sum(
        c.impact_effort_hours for c in report.changes
        if c.change_kind == "modified" and c.impact_effort_hours > 0
    )
    old = dict(baseline.estimate_totals or {})
    new_low = old.get("low_hours", 0.0) + affected_hours
    new_likely = old.get("likely_hours", 0.0) + affected_hours * 1.5
    new_high = old.get("high_hours", 0.0) + affected_hours * 2.5

    scope = ScopeDocument(
        project_id=baseline.project_id,
        objective=f"Revised scope for {baseline.project_id} after follow-up {report.followup_transcript_id}",
        current_problem="See baseline proposal for initial problem statement.",
        agreed_requirement_ids=[r.requirement_id for r in baseline.requirements],
        proposed_solution="Deliver the baseline requirements with the changes recorded in the change report.",
        deliverables=list(baseline.deliverables),
        exclusions=list(baseline.exclusions),
        assumptions=[],
        dependencies=[],
        acceptance_criteria_by_req={r.requirement_id: list(r.acceptance_criteria) for r in baseline.requirements},
        client_responsibilities=[],
        open_questions=[q for c in report.changes for q in c.unresolved_questions],
        risks=[],
    )

    totals = EstimateTotals(
        low_hours=new_low,
        likely_hours=new_likely,
        high_hours=new_high,
        by_task={},
        by_requirement={},
    )

    draft = ProposalVersion(
        proposal_id=f"prop-rev-{uuid.uuid4()}",
        project_id=baseline.project_id,
        version=baseline.version + 1,
        status="revised",
        created_at=datetime.now(timezone.utc),
        executive_summary=f"Revised proposal (v{baseline.version + 1}) for {baseline.project_id} covering {len(report.changes)} detected changes.",
        client_problem="See baseline proposal.",
        solution=scope.proposed_solution,
        scope=scope,
        timeline_assumptions=["Revised estimates reflect modified requirements only; unchanged work is preserved."],
        estimate_totals=totals,
        pricing_assumptions=PricingAssumptions(),
        exclusions=list(baseline.exclusions),
        dependencies=[],
        risks=[],
        open_questions=scope.open_questions,
        next_steps="Await client approval of revised scope.",
        model_id="rebaseliner/deterministic-v1",
        prompt_version="v1",
        generated_by="rebaseliner",
        text_hash="",
    )
    draft.text_hash = _hash(f"{draft.executive_summary}|{new_likely}")
    return draft


def totals_delta(baseline: BaselineSnapshot, revised: ProposalVersion) -> dict[str, float]:
    old = baseline.estimate_totals or {}
    return {
        "low_hours_delta": revised.estimate_totals.low_hours - old.get("low_hours", 0.0),
        "likely_hours_delta": revised.estimate_totals.likely_hours - old.get("likely_hours", 0.0),
        "high_hours_delta": revised.estimate_totals.high_hours - old.get("high_hours", 0.0),
    }


def make_result(report: ChangeReport, revised: ProposalVersion) -> RevisedProposalResult:
    return RevisedProposalResult(
        report_id=report.report_id,
        revised_proposal_id=revised.proposal_id,
        revised_version=revised.version,
        requires_approval_before_send=True,
        sent_simulated=False,
        sent_at=None,
        sent_delivery_id=None,
    )
