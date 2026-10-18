"""Persistent ingestion-run tracking. Duplicate-run safe."""
from __future__ import annotations

import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS ingestion_runs (
    run_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    status TEXT NOT NULL,          -- queued | running | succeeded | failed | partial
    requested_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    counts_json TEXT,
    errors_json TEXT,
    requested_by TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_runs_status ON ingestion_runs(status);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._conn() as con:
            con.executescript(SCHEMA)

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

    def active_run(self, source: str) -> dict | None:
        with self._lock, self._conn() as con:
            row = con.execute(
                "SELECT * FROM ingestion_runs WHERE source=? AND status IN ('queued','running') ORDER BY requested_at DESC LIMIT 1",
                (source,),
            ).fetchone()
            return dict(row) if row else None

    def create(self, source: str, requested_by: str) -> dict:
        with self._lock, self._conn() as con:
            run_id = str(uuid.uuid4())
            ts = _now()
            con.execute(
                "INSERT INTO ingestion_runs (run_id, source, status, requested_at, requested_by) VALUES (?,?,?,?,?)",
                (run_id, source, "queued", ts, requested_by),
            )
            row = con.execute("SELECT * FROM ingestion_runs WHERE run_id=?", (run_id,)).fetchone()
            return dict(row)

    def get(self, run_id: str) -> dict | None:
        with self._conn() as con:
            row = con.execute("SELECT * FROM ingestion_runs WHERE run_id=?", (run_id,)).fetchone()
            return dict(row) if row else None

    def latest(self, source: str) -> dict | None:
        with self._conn() as con:
            row = con.execute(
                "SELECT * FROM ingestion_runs WHERE source=? ORDER BY requested_at DESC LIMIT 1",
                (source,),
            ).fetchone()
            return dict(row) if row else None

    def mark_running(self, run_id: str) -> None:
        with self._lock, self._conn() as con:
            con.execute("UPDATE ingestion_runs SET status='running', started_at=? WHERE run_id=?", (_now(), run_id))

    def mark_finished(self, run_id: str, status: str, counts_json: str, errors_json: str) -> None:
        with self._lock, self._conn() as con:
            con.execute(
                "UPDATE ingestion_runs SET status=?, finished_at=?, counts_json=?, errors_json=? WHERE run_id=?",
                (status, _now(), counts_json, errors_json, run_id),
            )
