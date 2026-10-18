"""Reject answers whose cited chunk IDs are not in the retrieved set."""
from __future__ import annotations

from ..schemas.qa import SourceRef


class CitationError(ValueError):
    pass


def validate_citations(sources: list[SourceRef], allowed_chunk_ids: set[int]) -> None:
    """
    Every source must have a chunk_id in allowed_chunk_ids.
    Raises CitationError on the first violation.
    """
    if not sources:
        return
    for s in sources:
        if s.chunk_id not in allowed_chunk_ids:
            raise CitationError(f"citation references chunk_id={s.chunk_id} which was not retrieved")

