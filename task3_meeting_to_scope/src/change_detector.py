"""Detect changes between a baseline snapshot and a follow-up extraction."""
from __future__ import annotations

from .matcher import match_requirements
from .out_of_scope import is_out_of_scope
from .schemas_3c import (
    BaselineRequirement,
    BaselineSnapshot,
    DetectedChange,
    FollowupRequirement,
    RequirementMatch,
)


def detect_changes(
    baseline: BaselineSnapshot,
    followup_reqs: list[FollowupRequirement],
    followup_decisions: list[dict],
    followup_commitments: list[dict],
) -> tuple[list[RequirementMatch], list[DetectedChange]]:
    matches = match_requirements(baseline.requirements, followup_reqs)
    match_by_fu = {m.followup_requirement_id: m for m in matches}
    changes: list[DetectedChange] = []

    # Per follow-up requirement
    for fu in followup_reqs:
        m = match_by_fu[fu.requirement_id]
        oos = is_out_of_scope(fu.source_quote) or is_out_of_scope(fu.description)

        if oos:
            changes.append(DetectedChange(
                change_kind="added",
                baseline_requirement_id=m.baseline_requirement_id,
                followup_requirement_id=fu.requirement_id,
                old_value=None,
                proposed_new_value=fu.description,
                evidence=[{"turn_id": fu.turn_id, "quote": fu.source_quote}],
                out_of_scope=True,
                unresolved_questions=["Confirm whether this is in scope for the current phase."],
                reviewer_confirmation_required=True,
            ))
            continue

        if m.match_status == "none":
            changes.append(DetectedChange(
                change_kind="added",
                baseline_requirement_id=None,
                followup_requirement_id=fu.requirement_id,
                old_value=None,
                proposed_new_value=fu.description,
                evidence=[{"turn_id": fu.turn_id, "quote": fu.source_quote}],
            ))
            continue

        if m.match_status == "ambiguous" or fu.tentative:
            changes.append(DetectedChange(
                change_kind="unresolved",
                baseline_requirement_id=m.baseline_requirement_id,
                followup_requirement_id=fu.requirement_id,
                old_value=_baseline_desc(baseline, m.baseline_requirement_id),
                proposed_new_value=fu.description,
                evidence=[{"turn_id": fu.turn_id, "quote": fu.source_quote}],
                unresolved_questions=(
                    ["Requirement tentatively mentioned; confirm scope with client."]
                    if fu.tentative
                    else ["Ambiguous match; reviewer must confirm mapping."]
                ),
                reviewer_confirmation_required=True,
            ))
            continue

        base = _baseline_for(baseline, m.baseline_requirement_id)
        if base and base.description.strip().lower() == fu.description.strip().lower():
            changes.append(DetectedChange(
                change_kind="unchanged",
                baseline_requirement_id=m.baseline_requirement_id,
                followup_requirement_id=fu.requirement_id,
                old_value=base.description,
                proposed_new_value=fu.description,
                evidence=[{"turn_id": fu.turn_id, "quote": fu.source_quote}],
            ))
        else:
            changes.append(DetectedChange(
                change_kind="modified",
                baseline_requirement_id=m.baseline_requirement_id,
                followup_requirement_id=fu.requirement_id,
                old_value=base.description if base else None,
                proposed_new_value=fu.description,
                evidence=[{"turn_id": fu.turn_id, "quote": fu.source_quote}],
                impact_effort_hours=4.0,
            ))

    # Removals: baseline requirements with no follow-up match
    matched_baseline_ids = {m.baseline_requirement_id for m in matches if m.baseline_requirement_id}
    for base in baseline.requirements:
        if base.requirement_id not in matched_baseline_ids:
            changes.append(DetectedChange(
                change_kind="removed",
                baseline_requirement_id=base.requirement_id,
                followup_requirement_id=None,
                old_value=base.description,
                proposed_new_value=None,
                evidence=[],
                impact_effort_hours=0.0,
                reviewer_confirmation_required=True,
            ))

    # Explicit removal decisions
    for dec in followup_decisions:
        if any(k in dec["source_quote"].lower() for k in ("drop", "remove", "not doing")):
            changes.append(DetectedChange(
                change_kind="removed",
                baseline_requirement_id=None,
                followup_requirement_id=None,
                old_value=dec["description"],
                proposed_new_value=None,
                evidence=[{"turn_id": dec["turn_id"], "quote": dec["source_quote"]}],
                reviewer_confirmation_required=True,
            ))

    # Deadline changes
    for com in followup_commitments:
        if com.get("deadline") and com.get("old_deadline"):
            changes.append(DetectedChange(
                change_kind="modified",
                baseline_requirement_id=None,
                followup_requirement_id=None,
                old_value=f"deadline={com['old_deadline']}",
                proposed_new_value=f"deadline={com['deadline']}",
                evidence=[{"turn_id": com["turn_id"], "quote": com["source_quote"]}],
                impact_effort_hours=0.0,
                reviewer_confirmation_required=True,
            ))

    return matches, changes


def _baseline_for(baseline: BaselineSnapshot, rid: str | None) -> BaselineRequirement | None:
    if not rid:
        return None
    for b in baseline.requirements:
        if b.requirement_id == rid:
            return b
    return None


def _baseline_desc(baseline: BaselineSnapshot, rid: str | None) -> str | None:
    b = _baseline_for(baseline, rid)
    return b.description if b else None
