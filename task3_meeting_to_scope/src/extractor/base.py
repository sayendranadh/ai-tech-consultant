from __future__ import annotations

from typing import Protocol

from ..ingestion.chunker import Chunk
from ..schemas import ExtractedRecord


class UnconfiguredModelError(RuntimeError):
    """Raised when a live model client is used without credentials."""


class Extractor(Protocol):
    prompt_version: str

    def extract(self, chunk: Chunk) -> list[ExtractedRecord]:
        ...
