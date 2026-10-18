"""Mock extractor: deterministic, keyed by chunk_id.

Fixtures are in data/mock_extractions.json. This mock makes the pipeline testable
end-to-end without claiming model accuracy.
"""
from __future__ import annotations

import json
from pathlib import Path

from ..ingestion.chunker import Chunk
from ..schemas import ExtractedRecord, TurnRef


class MockExtractor:
    def __init__(self, fixtures_path: Path) -> None:
        raw = json.loads(fixtures_path.read_text(encoding="utf-8"))
        self._fixtures: dict[str, list[dict]] = raw
        self.prompt_version = "mock-v1"

    def extract(self, chunk: Chunk) -> list[ExtractedRecord]:
        rows = self._fixtures.get(chunk.chunk_id, [])
        out: list[ExtractedRecord] = []
        for row in rows:
            refs = [
                TurnRef(
                    transcript_id=chunk.transcript_id,
                    turn_id=ref["turn_id"],
                    speaker=ref["speaker"],
                    timestamp=ref.get("timestamp"),
                    quote=ref["quote"],
                )
                for ref in row["source_refs"]
            ]
            out.append(ExtractedRecord(
                record_kind=row["record_kind"],
                text=row["text"],
                source_refs=refs,
                provenance=row["provenance"],
                confidence=row.get("confidence", "medium"),
            ))
        return out
