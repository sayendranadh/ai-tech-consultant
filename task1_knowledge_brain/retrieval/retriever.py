"""Hybrid retrieval. Configurable weights. Deactivated chunks are never returned."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .embedder import EmbeddingProvider
from .vector_store import ScoredChunk, VectorStore

log = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    chunks: list[ScoredChunk]
    mode: str  # "semantic" | "keyword" | "hybrid"


class Retriever:
    def __init__(
        self,
        db_path: Path,
        embedder: EmbeddingProvider,
        semantic_weight: float = 0.6,
        keyword_weight: float = 0.4,
    ) -> None:
        self._embedder = embedder
        self._store = VectorStore(db_path, dim=embedder.dim)
        self._sw = semantic_weight
        self._kw = keyword_weight

    def search(self, query: str, top_k: int = 10, mode: str = "hybrid") -> RetrievalResult:
        if not query.strip():
            return RetrievalResult(chunks=[], mode=mode)

        sem: list[ScoredChunk] = []
        kw: list[ScoredChunk] = []

        if mode in ("semantic", "hybrid"):
            qv = self._embedder.embed([query])[0]
            sem = self._store.search(qv, top_k=top_k, model_id=self._embedder.model_id)

        if mode in ("keyword", "hybrid"):
            try:
                kw = self._store.keyword_search(query, top_k=top_k)
            except Exception as exc:  # noqa: BLE001
                log.warning("keyword search failed (%s); falling back to semantic only", exc)
                kw = []

        if mode == "semantic":
            return RetrievalResult(chunks=sem, mode="semantic")
        if mode == "keyword":
            return RetrievalResult(chunks=kw, mode="keyword")

        # Hybrid: normalize each list to [0,1] then weighted sum.
        def _normalize(items: list[ScoredChunk]) -> dict[int, float]:
            if not items:
                return {}
            scores = [c.score for c in items]
            lo, hi = min(scores), max(scores)
            if hi == lo:
                return {c.chunk_id: 1.0 for c in items}
            return {c.chunk_id: (c.score - lo) / (hi - lo) for c in items}

        sem_n = _normalize(sem)
        kw_n = _normalize(kw)
        by_id: dict[int, ScoredChunk] = {c.chunk_id: c for c in sem + kw}
        combined: list[ScoredChunk] = []
        for cid, ch in by_id.items():
            score = self._sw * sem_n.get(cid, 0.0) + self._kw * kw_n.get(cid, 0.0)
            combined.append(ScoredChunk(
                chunk_id=cid, url=ch.url, section_heading=ch.section_heading, text=ch.text, score=score,
            ))
        combined.sort(key=lambda c: c.score, reverse=True)
        return RetrievalResult(chunks=combined[:top_k], mode="hybrid")
