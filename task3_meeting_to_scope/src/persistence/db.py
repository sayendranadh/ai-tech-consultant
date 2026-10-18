"""SQLite persistence for Task 3A."""
from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS transcripts (
    transcript_id TEXT PRIMARY KEY,
    meeting_number INTEGER NOT NULL,
    project_id TEXT NOT NULL,
    meeting_date TEXT NOT NULL,
    is_synthetic INTEGER NOT NULL DEFAULT 1,
    raw_json TEXT NOT NULL,
    ingested_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS requirements (
    requirement_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (requirement_id, version)
);
CREATE INDEX IF NOT EXISTS idx_req_project ON requirements(project_id);

CREATE TABLE IF NOT EXISTS open_questions (
    question_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS extracted_records (
    record_id TEXT PRIMARY KEY,
    transcript_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    record_kind TEXT NOT NULL,
    json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_records_project ON extracted_records(project_id);

CREATE TABLE IF NOT EXISTS conflicts (
    conflict_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DAO:
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
        con.execute("PRAGMA foreign_keys=ON;")
        try:
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    def insert_transcript(self, t: dict) -> None:
        with self._conn() as con:
            con.execute(
                "INSERT OR REPLACE INTO transcripts (transcript_id, meeting_number, project_id, meeting_date, is_synthetic, raw_json, ingested_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (t["transcript_id"], t["meeting_number"], t["project_id"], t["meeting_date"],
                 1 if t.get("is_synthetic", True) else 0, json.dumps(t), _now()),
            )

    def get_transcript(self, transcript_id: str) -> dict | None:
        with self._conn() as con:
            row = con.execute("SELECT raw_json FROM transcripts WHERE transcript_id = ?", (transcript_id,)).fetchone()
        return json.loads(row["raw_json"]) if row else None

    def next_requirement_version(self, requirement_id: str) -> int:
        with self._conn() as con:
            row = con.execute("SELECT MAX(version) AS v FROM requirements WHERE requirement_id = ?", (requirement_id,)).fetchone()
        return int(row["v"] or 0) + 1

    def upsert_requirement(self, req: dict) -> int:
        rid = req["requirement_id"]
        version = self.next_requirement_version(rid)
        req = {**req, "version": version, "updated_version": version}
        with self._conn() as con:
            con.execute(
                "INSERT INTO requirements (requirement_id, project_id, version, json, created_at) VALUES (?, ?, ?, ?, ?)",
                (rid, req["project_id"], version, json.dumps(req), _now()),
            )
        return version

    def latest_requirements_for_project(self, project_id: str) -> list[dict]:
        with self._conn() as con:
            rows = con.execute(
                "SELECT r.json FROM requirements r "
                "INNER JOIN (SELECT requirement_id, MAX(version) AS maxv FROM requirements WHERE project_id = ? GROUP BY requirement_id) latest "
                "ON r.requirement_id = latest.requirement_id AND r.version = latest.maxv "
                "WHERE r.project_id = ?",
                (project_id, project_id),
            ).fetchall()
        return [json.loads(row["json"]) for row in rows]

    def upsert_open_question(self, q: dict) -> None:
        with self._conn() as con:
            con.execute(
                "INSERT OR REPLACE INTO open_questions (question_id, project_id, json, created_at) VALUES (?, ?, ?, ?)",
                (q["question_id"], q["project_id"], json.dumps(q), _now()),
            )

    def open_questions_for_project(self, project_id: str) -> list[dict]:
        with self._conn() as con:
            rows = con.execute("SELECT json FROM open_questions WHERE project_id = ?", (project_id,)).fetchall()
        return [json.loads(row["json"]) for row in rows]

    def insert_extracted_records(self, project_id: str, transcript_id: str, records: list[dict]) -> None:
        with self._conn() as con:
            for r in records:
                con.execute(
                    "INSERT INTO extracted_records (record_id, transcript_id, project_id, record_kind, json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (str(uuid.uuid4()), transcript_id, project_id, r["record_kind"], json.dumps(r), _now()),
                )

    def insert_conflict(self, c: dict) -> None:
        with self._conn() as con:
            con.execute(
                "INSERT OR REPLACE INTO conflicts (conflict_id, project_id, json, created_at) VALUES (?, ?, ?, ?)",
                (c["conflict_id"], c["project_id"], json.dumps(c), _now()),
            )

    def conflicts_for_project(self, project_id: str) -> list[dict]:
        with self._conn() as con:
            rows = con.execute("SELECT json FROM conflicts WHERE project_id = ?", (project_id,)).fetchall()
        return [json.loads(row["json"]) for row in rows]
