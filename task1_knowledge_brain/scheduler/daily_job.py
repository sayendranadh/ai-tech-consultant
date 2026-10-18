"""Daily incremental ingestion. Module-level functions — picklable for SQLAlchemyJobStore.

Two entry points:
- run_daily_ingestion(source: str = "") — scheduled by APScheduler.
- run_daily_ingestion_manual(limit: int | None = None, dry_run: bool = False) — CLI / tests.

Both delegate to _run_inner, which:
1. Serializes on a DB-level lock per source (SQLite BEGIN IMMEDIATE).
2. Fetches sitemap (recursive index), classifies changes.
3. Ingests new/updated; deactivates removed chunks (via orchestrator).
4. Persists run status in ingestion_runs (same table as 1C).
5. Recovers interrupted runs.
"""
from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone

from ..ingestion.config import IngestionConfig
from ..ingestion.orchestrator import run_ingestion
from .change_detector import classify  # noqa: F401  (used indirectly via orchestrator)

log = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _acquire_source_lock(cfg: IngestionConfig, source: str) -> sqlite3.Connection:
    """Open a connection in IMMEDIATE mode to serialize runs on this source."""
    con = sqlite3.connect(cfg.db_path, timeout=0.0, isolation_level=None)
    con.execute("PRAGMA journal_mode=WAL;")
    try:
        con.execute("BEGIN IMMEDIATE")
    except sqlite3.OperationalError as exc:
        con.close()
        raise RuntimeError(f"another run holds the lock for {source}: {exc}") from exc
    return con


def _record_run(cfg: IngestionConfig, run_id: str, source: str, status: str, counts: dict, errors: list) -> None:
    con = sqlite3.connect(cfg.db_path)
    try:
        con.execute(
            "INSERT INTO ingestion_runs (run_id, source, status, requested_at, started_at, finished_at, counts_json, errors_json, requested_by) "
            "VALUES (?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(run_id) DO UPDATE SET status=excluded.status, finished_at=excluded.finished_at, "
            "counts_json=excluded.counts_json, errors_json=excluded.errors_json",
            (run_id, source, status, _now(), _now(), _now(), json.dumps(counts), json.dumps(errors), "scheduler"),
        )
        con.commit()
    finally:
        con.close()


def run_daily_ingestion(source: str = "") -> None:
    """APScheduler entry point. No args from scheduler; reads config from env."""
    cfg = IngestionConfig()
    src = source or cfg.source_domain
    asyncio.run(_run_inner(cfg, src, limit=None, dry_run=False))


def run_daily_ingestion_manual(limit: int | None = None, dry_run: bool = False) -> None:
    """CLI / tests entry point."""
    cfg = IngestionConfig()
    asyncio.run(_run_inner(cfg, cfg.source_domain, limit=limit, dry_run=dry_run))


async def _run_inner(cfg: IngestionConfig, source: str, limit: int | None, dry_run: bool) -> None:
    run_id = str(uuid.uuid4())
    lock_con = None
    try:
        lock_con = _acquire_source_lock(cfg, source)
    except RuntimeError as exc:
        log.warning("skipping daily run: %s", exc)
        _record_run(cfg, run_id, source, "failed", {}, [{"code": "lock_held", "message": str(exc)}])
        return
    try:
        _record_run(cfg, run_id, source, "running", {}, [])
        report = await run_ingestion(cfg, limit=limit, dry_run=dry_run)
        status = "succeeded" if not report.errors else "partial"
        _record_run(cfg, run_id, source, status, report.counts, report.errors)
        log.info("daily run %s finished: status=%s counts=%s", run_id, status, report.counts)
    except Exception as exc:  # noqa: BLE001
        log.exception("daily run %s crashed", run_id)
        _record_run(cfg, run_id, source, "failed", {}, [{"code": "crash", "message": str(exc)}])
    finally:
        if lock_con is not None:
            try:
                lock_con.execute("COMMIT")
            except sqlite3.OperationalError:
                pass
            lock_con.close()
