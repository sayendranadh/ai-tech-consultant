"""Re-validate critical extracted claims against the original transcript."""
from __future__ import annotations

import re

from ..schemas import Requirement, Transcript


def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def validate_requirements(requirements: list[Requirement], transcripts: dict[str, Transcript]) -> list[dict]:
    issues: list[dict] = []
    for req in requirements:
        if not req.source_refs:
            issues.append({"requirement_id": req.requirement_id, "kind": "missing_source", "detail": "no source_refs"})
            continue
        if req.provenance != "client_stated":
            continue
        for ref in req.source_refs:
            transcript = transcripts.get(ref.transcript_id)
            if transcript is None:
                issues.append({"requirement_id": req.requirement_id, "kind": "missing_source", "detail": f"transcript {ref.transcript_id} not found"})
                continue
            turn = next((t for t in transcript.turns if t.turn_id == ref.turn_id), None)
            if turn is None:
                issues.append({"requirement_id": req.requirement_id, "kind": "missing_source", "detail": f"turn {ref.turn_id} not found"})
                continue
            if _normalize(ref.quote) not in _normalize(turn.text):
                issues.append({"requirement_id": req.requirement_id, "kind": "unsupported_claim", "detail": f"quote not in turn {ref.turn_id}"})
    return issues
