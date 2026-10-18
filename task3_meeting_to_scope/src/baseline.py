"""Load the approved baseline for a project from fixtures (or a DB in a future milestone)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .schemas_3c import BaselineRequirement, BaselineSnapshot


def load_baseline(project_id: str, fixture_path: Path) -> BaselineSnapshot:
    raw = json.loads(fixture_path.read_text(encoding="utf-8"))
    row = raw.get(project_id)
    if row is None:
        raise KeyError(f"no baseline for project {project_id}")
    reqs = [
        BaselineRequirement(
            requirement_id=r["requirement_id"],
            description=r["description"],
            source_quote=r["source_quote"],
            acceptance_criteria=list(r.get("acceptance_criteria", [])),
            deadline=r.get("deadline"),
        )
        for r in row["requirements"]
    ]
    return BaselineSnapshot(
        project_id=project_id,
        proposal_id=row["proposal_id"],
        version=int(row["version"]),
        status="approved",
        approved_by=row["approved_by"],
        requirements=reqs,
        estimate_totals=dict(row.get("estimate_totals", {})),
        deliverables=list(row.get("deliverables", [])),
        exclusions=list(row.get("exclusions", [])),
        captured_at=datetime.now(timezone.utc),
    )
