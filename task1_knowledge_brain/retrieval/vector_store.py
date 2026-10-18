"""Persist and query embeddings. Uses sqlite-vec when available; falls back to in-memory cosine.

PREREQUISITE: the ingestion schema must exist. `_bootstrap` instantiates
`ManifestStore` first (safe, idempotent) so this module works even when called
against a fresh DB without a prior ingestion run.
"""
from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from ..ingestion.manifest import ManifestStore  # 1A schema — guaranteed bootstrap
from .embedder import blob_to_vector, vector_to_blob
from .schema import EMBEDDING_SCHEMA

log = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ScoredChunk:
    chunk_id: int
    url: str
    section_heading: str | None
    text: str
    score: float  # cosine similarity in [-1, 1] — see ADR-018


class VectorStore:
    def __init__(self, db_path: Path, dim: int) -> None:
        self.db_path = Path(db_path)
        self.dim = dim
        self.uses_sqlite_vec = False
        self._bootstrap()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL;")
        try:
            con.enable_load_extension(True)
            import sqlite_vec  # type: ignore
            sqlite_vec.load(con)
            con.enable_load_extension(False)
            self.uses_sqlite_vec = True
        except Exception as exc:  # noqa: BLE001
            log.info("sqlite-vec unavailable (%s); using in-memory cosine fallback", exc)
            self.uses_sqlite_vec = False
        return con

    def _bootstrap(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # Ensure 1A schema exists first. ManifestStore is idempotent (CREATE IF NOT EXISTS).
        ManifestStore(self.db_path)
        con = self._connect()
        try:
            con.executescript(EMBEDDING_SCHEMA)
            # Backfill FTS5 from any pre-existing chunks. 'rebuild' is idempotent.
            con.execute("INSERT INTO chunks_fts(chunks_fts) VALUES('rebuild');")
            con.commit()
        finally:
            con.close()
        if not self.uses_sqlite_vec:
            log.warning("VECTOR SEARCH FALLBACK: sqlite-vec unavailable; using in-memory cosine. "
                        "Document this limitation in the capability report.")

    # --- write ---------------------------------------------------------
    def upsert_chunk_embeddings(self, rows: list[tuple[int, str, np.ndarray]]) -> int:
        written = 0
        con = self._connect()
        try:
            for chunk_id, model_id, vec in rows:
                con.execute(
                    """
                    INSERT INTO chunk_embeddings (chunk_id, model_id, dim, vec, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(chunk_id) DO UPDATE SET
                        model_id=excluded.model_id, dim=excluded.dim,
                        vec=excluded.vec, created_at=excluded.created_at
                    """,
                    (chunk_id, model_id, self.dim, vector_to_blob(vec), _now()),
                )
                written += 1
            con.commit()
            return written
        finally:
            con.close()

    def deactivate_missing_embeddings(self) -> int:
        con = self._connect()
        try:
            cur = con.execute(
                "DELETE FROM chunk_embeddings WHERE chunk_id IN "
                "(SELECT ce.chunk_id FROM chunk_embeddings ce LEFT JOIN chunks c ON c.id = ce.chunk_id "
                " WHERE c.id IS NULL OR c.is_active = 0)"
            )
            con.commit()
            return cur.rowcount
        finally:
            con.close()

    # --- read ----------------------------------------------------------
    def search(
        self,
        query_vec: np.ndarray,
        top_k: int = 10,
        model_id: str | None = None,
    ) -> list[ScoredChunk]:
        """Return top-k active chunks by cosine similarity. Score range is [-1, 1] (ADR-018)."""
        con = self._connect()
        try:
            params: list = []
            where = "WHERE c.is_active = 1"
            if model_id:
                where += " AND ce.model_id = ?"
                params.append(model_id)
            rows = con.execute(
                f"""
                SELECT ce.chunk_id, ce.vec, ce.dim, c.url, c.section_heading, c.text
                FROM chunk_embeddings ce JOIN chunks c ON c.id = ce.chunk_id
                {where}
                """,
                params,
            ).fetchall()
            if not rows:
                return []
            q = query_vec.astype(np.float32)
            q = q / (np.linalg.norm(q) or 1.0)
            scored: list[ScoredChunk] = []
            for r in rows:
                v = blob_to_vector(r["vec"], int(r["dim"]))
                v = v / (np.linalg.norm(v) or 1.0)
                score = float(np.dot(q, v))  # in [-1, 1]
                scored.append(ScoredChunk(
                    chunk_id=int(r["chunk_id"]), url=r["url"],
                    section_heading=r["section_heading"], text=r["text"], score=score,
                ))
            scored.sort(key=lambda s: s.score, reverse=True)
            return scored[:top_k]
        finally:
            con.close()

    def keyword_search(self, query: str, top_k: int = 10) -> list[ScoredChunk]:
        con = self._connect()
        try:
            import re as _re
            clean = _re.sub(r'[?*():"\\-]', ' ', query).strip()
            if not clean:
                return []
            safe_query = clean
            rows = con.execute(
                """
                SELECT c.id AS chunk_id, c.url, c.section_heading, c.text, bm25(chunks_fts) AS rank
                FROM chunks_fts JOIN chunks c ON c.id = chunks_fts.rowid
                WHERE chunks_fts MATCH ? AND c.is_active = 1
                ORDER BY rank ASC
                LIMIT ?
                """,
                (safe_query, top_k),
            ).fetchall()
            return [
                ScoredChunk(
                    chunk_id=int(r["chunk_id"]), url=r["url"],
                    section_heading=r["section_heading"], text=r["text"], score=-float(r["rank"]),
                )
                for r in rows
            ]
        finally:
            con.close()
