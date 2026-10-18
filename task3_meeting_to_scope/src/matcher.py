"""Requirement matching: baseline vs follow-up, token-set Jaccard on source_quote.

- >= 0.5 -> confirmed
- >= 0.3 -> ambiguous
- else   -> none
"""
from __future__ import annotations

import re

from .schemas_3c import BaselineRequirement, FollowupRequirement, RequirementMatch

CONFIRM_THRESHOLD = 0.5
AMBIGUOUS_THRESHOLD = 0.3


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _jaccard(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def match_requirements(
    baseline: list[BaselineRequirement],
    followup: list[FollowupRequirement],
) -> list[RequirementMatch]:
    matches: list[RequirementMatch] = []
    for fu in followup:
        best_base: BaselineRequirement | None = None
        best_sim = 0.0
        for base in baseline:
            sim = _jaccard(base.source_quote, fu.source_quote)
            if sim > best_sim:
                best_sim = sim
                best_base = base
        if best_base is not None and best_sim >= CONFIRM_THRESHOLD:
            matches.append(RequirementMatch(
                baseline_requirement_id=best_base.requirement_id,
                followup_requirement_id=fu.requirement_id,
                match_status="confirmed",
                similarity=round(best_sim, 3),
                rationale=f"token Jaccard >= {CONFIRM_THRESHOLD}",
            ))
        elif best_base is not None and best_sim >= AMBIGUOUS_THRESHOLD:
            matches.append(RequirementMatch(
                baseline_requirement_id=best_base.requirement_id,
                followup_requirement_id=fu.requirement_id,
                match_status="ambiguous",
                similarity=round(best_sim, 3),
                rationale=f"token Jaccard in [{AMBIGUOUS_THRESHOLD}, {CONFIRM_THRESHOLD}); reviewer confirmation required",
            ))
        else:
            matches.append(RequirementMatch(
                baseline_requirement_id=None,
                followup_requirement_id=fu.requirement_id,
                match_status="none",
                similarity=round(best_sim, 3),
                rationale="no baseline match above ambiguous threshold",
            ))
    return matches
