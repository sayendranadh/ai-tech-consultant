"""SQLite manifest + storage. Idempotent upserts. No raw HTTP here."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS manifest (
    url TEXT PRIMARY KEY,
    content_hash TEXT,
    sitemap_lastmod TEXT,
    processing_status TEXT NOT NULL DEFAULT 'pending',
    extraction_version INTEGER NOT NULL DEFAULT 1,
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    added_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    removed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_manifest_status ON manifest(processing_status);

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL,
    version INTEGER NOT NULL,
    title TEXT,
    body_text TEXT NOT NULL,
    canonical_url TEXT,
    content_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(url, version)
);
CREATE INDEX IF NOT EXISTS idx_documents_url ON documents(url);

CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    url TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    section_heading TEXT,
    content_hash TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    UNIQUE(document_id, chunk_index),
    FOREIGN KEY(document_id) REFERENCES documents(id)
);
CREATE INDEX IF NOT EXISTS idx_chunks_url ON chunks(url);
CREATE INDEX IF NOT EXISTS idx_chunks_active ON chunks(url, is_active);

CREATE TABLE IF NOT EXISTS images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_url TEXT NOT NULL,
    src TEXT NOT NULL,
    alt TEXT,
    section_heading TEXT,
    content_hash TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    UNIQUE(article_url, src)
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ManifestStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as con:
            con.executescript(SCHEMA)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row          # <-- FIX
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

    # --- manifest -------------------------------------------------------
    def get(self, url: str) -> sqlite3.Row | None:
        with self._conn() as con:
            return con.execute("SELECT * FROM manifest WHERE url = ?", (url,)).fetchone()

    def upsert_pending(self, url: str, sitemap_lastmod: str | None) -> None:
        ts = _now()
        with self._conn() as con:
            con.execute(
                """
                INSERT INTO manifest (url, sitemap_lastmod, processing_status, added_at, updated_at)
                VALUES (?, ?, 'pending', ?, ?)
                ON CONFLICT(url) DO UPDATE SET
                    sitemap_lastmod = excluded.sitemap_lastmod,
                    updated_at = excluded.updated_at
                """,
                (url, sitemap_lastmod, ts, ts),
            )

    def mark_status(self, url: str, status: str, error: str | None = None, bump_attempts: bool = False) -> None:
        with self._conn() as con:
            con.execute(
                "UPDATE manifest SET processing_status = ?, last_error = ?, updated_at = ?, attempts = attempts + ? WHERE url = ?",
                (status, error, _now(), 1 if bump_attempts else 0, url),
            )

    def mark_processed(self, url: str, content_hash: str, extraction_version: int) -> None:
        with self._conn() as con:
            con.execute(
                "UPDATE manifest SET processing_status='processed', content_hash=?, extraction_version=?, updated_at=? WHERE url=?",
                (content_hash, extraction_version, _now(), url),
            )

    def mark_removed(self, url: str) -> None:
        with self._conn() as con:
            con.execute("UPDATE manifest SET processing_status='removed', removed_at=?, updated_at=? WHERE url=?", (_now(), _now(), url))
            con.execute("UPDATE chunks SET is_active=0 WHERE url=?", (url,))
            con.execute("UPDATE images SET is_active=0 WHERE article_url=?", (url,))

    def list_active_urls(self) -> list[str]:
        with self._conn() as con:
            return [r["url"] for r in con.execute("SELECT url FROM manifest WHERE processing_status != 'removed'")]

    def list_in_progress(self) -> list[str]:
        with self._conn() as con:
            return [r["url"] for r in con.execute("SELECT url FROM manifest WHERE processing_status = 'in_progress'")]

    # --- documents ------------------------------------------------------
    def next_version(self, url: str) -> int:
        with self._conn() as con:
            row = con.execute("SELECT MAX(version) AS v FROM documents WHERE url = ?", (url,)).fetchone()
            return int(row["v"] or 0) + 1

    def write_document(self, url: str, title: str | None, body_text: str, canonical_url: str | None, content_hash: str) -> int:
        with self._conn() as con:
            cur = con.execute(
                "INSERT INTO documents (url, version, title, body_text, canonical_url, content_hash, created_at) VALUES (?,?,?,?,?,?,?)",
                (url, self.next_version(url), title, body_text, canonical_url, content_hash, _now()),
            )
            return int(cur.lastrowid)

    def write_chunks(self, document_id: int, url: str, chunks: list[tuple[int, str, str | None, str]]) -> int:
        written = 0
        with self._conn() as con:
            for idx, text, section, chash in chunks:
                cur = con.execute(
                    "INSERT OR IGNORE INTO chunks (document_id, url, chunk_index, text, section_heading, content_hash, is_active, created_at) VALUES (?,?,?,?,?,?,1,?)",
                    (document_id, url, idx, text, section, chash, _now()),
                )
                written += cur.rowcount
        return written

    def deactivate_stale_chunks(self, url: str, keep_document_id: int) -> int:
        with self._conn() as con:
            cur = con.execute("UPDATE chunks SET is_active=0 WHERE url=? AND document_id<>?", (url, keep_document_id))
            return cur.rowcount

    # --- images ---------------------------------------------------------
    def write_images(self, article_url: str, images: list[tuple[str, str | None, str | None, str]]) -> int:
        written = 0
        with self._conn() as con:
            for src, alt, section, chash in images:
                cur = con.execute(
                    "INSERT OR IGNORE INTO images (article_url, src, alt, section_heading, content_hash, is_active, created_at) VALUES (?,?,?,?,?,1,?)",
                    (article_url, src, alt, section, chash, _now()),
                )
                written += cur.rowcount
        return written

    # --- test/ops helpers ----------------------------------------------
    def count(self, table: str) -> int:
        if table not in {"manifest", "documents", "chunks", "images"}:
            raise ValueError(f"unexpected table: {table}")
        with self._conn() as con:
            return int(con.execute(f"SELECT COUNT(*) AS c FROM {table}").fetchone()["c"])

    def status_counts(self) -> dict[str, int]:
        with self._conn() as con:
            rows = con.execute("SELECT processing_status AS s, COUNT(*) AS c FROM manifest GROUP BY processing_status").fetchall()
            return {r["s"]: int(r["c"]) for r in rows}

    def get_row(self, url: str) -> dict[str, Any] | None:
        row = self.get(url)
        return dict(row) if row is not None else None
