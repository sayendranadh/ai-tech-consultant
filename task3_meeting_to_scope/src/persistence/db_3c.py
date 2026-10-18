"""3C persistence: change reports, revised proposals, deliveries. Additive to 3A/3B."""
from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS change_reports (
    report_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    baseline_proposal_id TEXT NOT NULL,
    baseline_version INTEGER NOT NULL,
    followup_transcript_id TEXT NOT NULL,
    approved INTEGER NOT NULL DEFAULT 0,
    approved_by TEXT,
    approved_at TEXT,
    json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cr_project ON change_reports(project_id);

CREATE TABLE IF NOT EXISTS revised_proposals (
    proposal_id TEXT PRIMARY KEY,
    report_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    status TEXT NOT NULL,
    json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS change_report_deliveries (
    delivery_id TEXT PRIMARY KEY,
    report_id TEXT NOT NULL,
    proposal_id TEXT NOT NULL,
    mode TEXT NOT NULL,
    is_simulated INTEGER NOT NULL DEFAULT 1,
    delivery_status TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DAO3C:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
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

    def insert_change_report(self, report: dict) -> None:
        with self._conn() as con:
            con.execute(
                "INSERT OR REPLACE INTO change_reports "
                "(report_id, project_id, baseline_proposal_id, baseline_version, followup_transcript_id, approved, approved_by, approved_at, json, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    report["report_id"], report["project_id"], report["baseline_proposal_id"],
                    report["baseline_version"], report["followup_transcript_id"],
                    1 if report.get("approved") else 0,
                    report.get("approved_by"), report.get("approved_at"),
                    json.dumps(report, default=str), _now(),
                ),
            )

    def get_change_report(self, report_id: str) -> dict | None:
        with self._conn() as con:
            row = con.execute("SELECT json FROM change_reports WHERE report_id = ?", (report_id,)).fetchone()
        return json.loads(row["json"]) if row else None

    def mark_report_approved(self, report_id: str, approved_by: str) -> dict:
        with self._conn() as con:
            row = con.execute("SELECT json FROM change_reports WHERE report_id = ?", (report_id,)).fetchone()
            if not row:
                raise KeyError(report_id)
            data = json.loads(row["json"])
            ts = _now()
            data["approved"] = True
            data["approved_by"] = approved_by
            data["approved_at"] = ts
            con.execute(
                "UPDATE change_reports SET approved = 1, approved_by = ?, approved_at = ?, json = ? WHERE report_id = ?",
                (approved_by, ts, json.dumps(data, default=str), report_id),
            )
        return data

    def insert_revised_proposal(self, report_id: str, project_id: str, proposal: dict) -> None:
        with self._conn() as con:
            con.execute(
                "INSERT OR REPLACE INTO revised_proposals (proposal_id, report_id, project_id, version, status, json, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (proposal["proposal_id"], report_id, project_id, proposal["version"], proposal["status"], json.dumps(proposal, default=str), _now()),
            )

    def get_revised_proposal_by_report(self, report_id: str) -> dict | None:
        with self._conn() as con:
            row = con.execute("SELECT json FROM revised_proposals WHERE report_id = ? ORDER BY version DESC LIMIT 1", (report_id,)).fetchone()
        return json.loads(row["json"]) if row else None

    def insert_delivery(self, report_id: str, proposal_id: str) -> str:
        did = str(uuid.uuid4())
        with self._conn() as con:
            con.execute(
                "INSERT INTO change_report_deliveries (delivery_id, report_id, proposal_id, mode, is_simulated, delivery_status, created_at) "
                "VALUES (?, ?, ?, 'simulated', 1, 'simulated_sent', ?)",
                (did, report_id, proposal_id, _now()),
            )
        return did
