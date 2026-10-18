"""3B persistence. Additive to 3A; does not touch 3A tables."""
from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS feasibility_checks (
    requirement_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (requirement_id, version)
);

CREATE TABLE IF NOT EXISTS estimate_tasks (
    task_id TEXT PRIMARY KEY,
    requirement_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS proposals (
    proposal_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    status TEXT NOT NULL,
    json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (proposal_id, version)
);
CREATE INDEX IF NOT EXISTS idx_proposals_project ON proposals(project_id);

CREATE TABLE IF NOT EXISTS proposal_approvals (
    approval_id TEXT PRIMARY KEY,
    proposal_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    approved_by TEXT NOT NULL,
    approval_text_hash TEXT NOT NULL,
    json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_approvals_proposal ON proposal_approvals(proposal_id);

CREATE TABLE IF NOT EXISTS proposal_deliveries (
    delivery_id TEXT PRIMARY KEY,
    proposal_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    mode TEXT NOT NULL,
    is_simulated INTEGER NOT NULL DEFAULT 1,
    delivery_status TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DAO3B:
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

    def insert_feasibility_check(self, project_id: str, check: dict) -> None:
        with self._conn() as con:
            ver = con.execute(
                "SELECT COALESCE(MAX(version), 0) + 1 AS v FROM feasibility_checks WHERE requirement_id = ?",
                (check["requirement_id"],),
            ).fetchone()["v"]
            con.execute(
                "INSERT INTO feasibility_checks (requirement_id, project_id, version, json, created_at) VALUES (?, ?, ?, ?, ?)",
                (check["requirement_id"], project_id, ver, json.dumps(check, default=str), _now()),
            )

    def latest_feasibility_checks(self, project_id: str) -> list[dict]:
        with self._conn() as con:
            rows = con.execute(
                "SELECT f.json FROM feasibility_checks f "
                "INNER JOIN (SELECT requirement_id, MAX(version) AS mv FROM feasibility_checks WHERE project_id = ? GROUP BY requirement_id) l "
                "ON f.requirement_id = l.requirement_id AND f.version = l.mv WHERE f.project_id = ?",
                (project_id, project_id),
            ).fetchall()
        return [json.loads(r["json"]) for r in rows]

    def insert_estimate_task(self, project_id: str, task: dict) -> None:
        with self._conn() as con:
            con.execute(
                "INSERT OR REPLACE INTO estimate_tasks (task_id, requirement_id, project_id, json, created_at) VALUES (?, ?, ?, ?, ?)",
                (task["task_id"], task["requirement_id"], project_id, json.dumps(task, default=str), _now()),
            )

    def insert_proposal(self, proposal: dict) -> None:
        with self._conn() as con:
            con.execute(
                "INSERT INTO proposals (proposal_id, project_id, version, status, json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (proposal["proposal_id"], proposal["project_id"], proposal["version"], proposal["status"], json.dumps(proposal, default=str), _now()),
            )

    def get_proposal(self, proposal_id: str, version: int | None = None) -> dict | None:
        with self._conn() as con:
            if version is not None:
                row = con.execute("SELECT json FROM proposals WHERE proposal_id = ? AND version = ?", (proposal_id, version)).fetchone()
            else:
                row = con.execute("SELECT json FROM proposals WHERE proposal_id = ? ORDER BY version DESC LIMIT 1", (proposal_id,)).fetchone()
        return json.loads(row["json"]) if row else None

    def get_latest_approved(self, proposal_id: str) -> dict | None:
        with self._conn() as con:
            row = con.execute(
                "SELECT p.json FROM proposals p WHERE p.proposal_id = ? AND p.status = 'approved' ORDER BY p.version DESC LIMIT 1",
                (proposal_id,),
            ).fetchone()
        return json.loads(row["json"]) if row else None

    def insert_approval(self, approval: dict) -> None:
        with self._conn() as con:
            con.execute(
                "INSERT INTO proposal_approvals (approval_id, proposal_id, version, approved_by, approval_text_hash, json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), approval["proposal_id"], approval["version"], approval["approved_by"], approval["approval_text_hash"], json.dumps(approval, default=str), _now()),
            )
            con.execute("UPDATE proposals SET status = 'approved' WHERE proposal_id = ? AND version = ?", (approval["proposal_id"], approval["version"]))

    def insert_delivery(self, proposal_id: str, version: int, mode: str, delivery_status: str) -> str:
        did = str(uuid.uuid4())
        with self._conn() as con:
            con.execute(
                "INSERT INTO proposal_deliveries (delivery_id, proposal_id, version, mode, is_simulated, delivery_status, created_at) VALUES (?, ?, ?, ?, 1, ?, ?)",
                (did, proposal_id, version, mode, delivery_status, _now()),
            )
            con.execute("UPDATE proposals SET status = 'sent_simulated' WHERE proposal_id = ? AND version = ?", (proposal_id, version))
        return did
