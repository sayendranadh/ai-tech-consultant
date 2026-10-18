"""FixtureQAClient — labeled answers from a documented fixture file.

Activated by KB_QA_CLIENT=fixture. NEVER claims to be a live model.
Every answer is prefixed [FIXTURE]. Sources are synthetic documentation
for verification only.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..schemas.qa import ImageRef, QAResponse, SourceRef


class FixtureQAClient:
    is_live = False

    def __init__(self, fixtures_path: Path, model_id: str = "fixture/qa-v1", prompt_version: str = "v1") -> None:
        self._fixtures = json.loads(Path(fixtures_path).read_text(encoding="utf-8"))
        self.model_id = model_id
        self.prompt_version = prompt_version

    def _match(self, question: str) -> dict | None:
        q = question.strip().lower()
        if q in self._fixtures:
            return self._fixtures[q]
        best_key = None
        for k in self._fixtures:
            if k in q:
                if best_key is None or len(k) > len(best_key):
                    best_key = k
        return self._fixtures[best_key] if best_key else None

    def structured_answer(self, question: str) -> QAResponse | None:
        row = self._match(question)
        if row is None:
            return None
        return QAResponse(
            question=question,
            status=row["status"],
            answer=row["answer"],
            sources=[SourceRef(**s) for s in row.get("sources", [])],
            image_refs=[ImageRef(**i) for i in row.get("image_refs", [])],
            escalation_required=bool(row.get("escalation_required", False)),
        )

    def answer(self, system: str, user: str) -> str:
        m = re.search(r"QUESTION:\s*\n(.+)", user)
        q = (m.group(1) if m else user).strip()
        resp = self.structured_answer(q)
        return "INSUFFICIENT" if resp is None else resp.answer
