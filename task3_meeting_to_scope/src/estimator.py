"""Deterministic estimator. Totals computed in Python, never by a model."""
from __future__ import annotations

import json
from pathlib import Path

from .schemas_3b import EstimateTask, EstimateTaskKind, EstimateTotals


TASK_KINDS: tuple[EstimateTaskKind, ...] = (
    "requirements_clarification", "technical_design",
    "backend_implementation", "frontend_implementation",
    "integration", "testing", "deployment", "documentation",
)


def build_tasks_from_fixtures(requirement_ids: list[str], fixture_path: Path) -> list[EstimateTask]:
    fix = json.loads(fixture_path.read_text(encoding="utf-8"))
    out: list[EstimateTask] = []
    for rid in requirement_ids:
        for i, row in enumerate(fix.get(rid, [])):
            out.append(EstimateTask(
                task_id=f"{rid}-T{i + 1:02d}",
                requirement_id=rid,
                task=row["task"],
                low_hours=float(row["low"]),
                likely_hours=float(row["likely"]),
                high_hours=float(row["high"]),
                rationale=row["rationale"],
                assumptions=list(row.get("assumptions", [])),
                dependencies=list(row.get("dependencies", [])),
                uncertainty="medium",
                reviewer_status="provisional_unreviewed",
            ))
    return out


def aggregate(tasks: list[EstimateTask]) -> EstimateTotals:
    low = sum(t.low_hours for t in tasks)
    likely = sum(t.likely_hours for t in tasks)
    high = sum(t.high_hours for t in tasks)
    by_task: dict[str, dict[str, float]] = {}
    by_req: dict[str, dict[str, float]] = {}
    for t in tasks:
        by_task.setdefault(t.task, {"low": 0.0, "likely": 0.0, "high": 0.0})
        by_task[t.task]["low"] += t.low_hours
        by_task[t.task]["likely"] += t.likely_hours
        by_task[t.task]["high"] += t.high_hours
        by_req.setdefault(t.requirement_id, {"low": 0.0, "likely": 0.0, "high": 0.0})
        by_req[t.requirement_id]["low"] += t.low_hours
        by_req[t.requirement_id]["likely"] += t.likely_hours
        by_req[t.requirement_id]["high"] += t.high_hours
    return EstimateTotals(low_hours=low, likely_hours=likely, high_hours=high, by_task=by_task, by_requirement=by_req)
