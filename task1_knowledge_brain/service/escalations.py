"""Escalation persistence with versioned resolutions and controlled promotion.

Promotion contract:
- Only `approved_for_general_knowledge=true` resolutions enter the retrieval store.
- Promotion creates a synthetic document (`source_type=expert_review`) via the same
  ingestion pipeline as crawled pages, idempotent on content hash.
- Customer-specific answers are persisted but NEVER promoted.
"""
from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

log = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS escalations (
    id TEXT PRIMARY KEY,
    question TEXT NOT NULL,
    reason TEXT NOT NULL,
    related_chunk_ids_json TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_by TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_esc_status ON escalations(status);

CREATE TABLE IF NOT EXISTS expert_answers (
    escalation_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    text TEXT NOT NULL,
    approved_for_general_knowledge INTEGER NOT NULL,
    approved_for_customer_specific INTEGER NOT NULL,
    approved_by TEXT NOT NULL,
    approved_at TEXT NOT NULL,
    promotion_run_id TEXT,
    promotion_error TEXT,
    PRIMARY KEY(escalation_id, version),
    FOREIGN KEY(escalation_id) REFERENCES escalations(id)
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class EscalationStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._conn() as con:
            con.executescript(SCHEMA)
            # Migration: add promotion_error if upgrading an existing DB.
            cols = {r["name"] for r in con.execute("PRAGMA table_info(expert_answers)").fetchall()}
            if "promotion_error" not in cols:
                con.execute("ALTER TABLE expert_answers ADD COLUMN promotion_error TEXT")

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL;")
        try:
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    def create(self, question: str, reason: str, related_chunk_ids: list[int], created_by: str) -> dict:
        with self._lock, self._conn() as con:
            eid = str(uuid.uuid4())
            ts = _now()
            con.execute(
                "INSERT INTO escalations (id, question, reason, related_chunk_ids_json, status, created_at, updated_at, created_by) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (eid, question, reason, json.dumps(related_chunk_ids), "open", ts, ts, created_by),
            )
            row = con.execute("SELECT * FROM escalations WHERE id=?", (eid,)).fetchone()
            return dict(row)

    def get(self, eid: str) -> dict | None:
        with self._conn() as con:
            row = con.execute("SELECT * FROM escalations WHERE id=?", (eid,)).fetchone()
            return dict(row) if row else None

    def resolve(
        self,
        eid: str,
        expert_answer: str,
        approved_for_general: bool,
        approved_for_customer: bool,
        approver: str,
        embedder=None,  # injected by the service layer so promotion can index
    ) -> dict:
        """
        Persist the resolution. If `approved_for_general=True` and `embedder` is provided,
        run promotion synchronously and populate `promotion_run_id`. Promotion failure does
        not roll back the resolution — it records `promotion_error` on the row and returns
        the row with `promotion_run_id=None`.
        """
        with self._lock, self._conn() as con:
            existing = con.execute("SELECT * FROM escalations WHERE id=?", (eid,)).fetchone()
            if not existing:
                raise KeyError(eid)
            version = con.execute(
                "SELECT COALESCE(MAX(version), 0) + 1 AS v FROM expert_answers WHERE escalation_id=?",
                (eid,),
            ).fetchone()["v"]
            ts = _now()
            con.execute(
                "INSERT INTO expert_answers (escalation_id, version, text, approved_for_general_knowledge, "
                "approved_for_customer_specific, approved_by, approved_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (eid, version, expert_answer, int(approved_for_general), int(approved_for_customer), approver, ts),
            )
            con.execute("UPDATE escalations SET status='resolved', updated_at=? WHERE id=?", (ts, eid))
            question = existing["question"]

        promotion_run_id: str | None = None
        promotion_error: str | None = None
        if approved_for_general:
            if embedder is None:
                promotion_error = "promotion skipped: no embedder provided"
                log.warning("escalation %s approved but embedder missing; promotion skipped", eid)
            else:
                try:
                    # Local import to avoid a hard dependency cycle at module load.
                    from ..scheduler.promotion import promote_escalation
                    from ..ingestion.config import IngestionConfig
                    cfg = IngestionConfig()
                    # Override DB path to the escalation store's own DB so tests are self-consistent.
                    cfg = cfg.model_copy(update={"db_path": self.db_path})
                    result = promote_escalation(cfg, embedder, eid, version)
                    promotion_run_id = result.promotion_run_id
                except Exception as exc:  # noqa: BLE001
                    promotion_error = f"{type(exc).__name__}: {exc}"
                    log.exception("promotion failed for escalation %s v%d", eid, version)

        # Persist promotion outcome (independent of resolution commit).
        with self._conn() as con:
            con.execute(
                "UPDATE expert_answers SET promotion_run_id=?, promotion_error=? "
                "WHERE escalation_id=? AND version=?",
                (promotion_run_id, promotion_error, eid, version),
            )
            row = con.execute(
                "SELECT * FROM expert_answers WHERE escalation_id=? AND version=?",
                (eid, version),
            ).fetchone()
            return dict(row)


def synthetic_document_url(escalation_id: str, version: int) -> str:
    return f"escalation://{escalation_id}/v{version}"


def synthetic_document_hash(question: str, answer: str) -> str:
    return hashlib.sha256(f"{question}\n---\n{answer}".encode("utf-8")).hexdigest()
