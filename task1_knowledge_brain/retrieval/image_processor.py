"""Process pending images: fetch (bounded), describe via VisionClient, persist."""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import httpx

from ..ingestion.config import IngestionConfig
from ..ingestion.fetcher import PoliteFetcher, PermanentFetchError, TransientFetchError
from .vision import ImageDescription, VisionClient

log = logging.getLogger(__name__)
MAX_IMAGE_BYTES = 8 * 1024 * 1024


@dataclass
class ImageProcessResult:
    processed: int = 0
    failed: int = 0
    skipped_unchanged: int = 0
    simulated: int = 0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def process_pending_images(
    cfg: IngestionConfig,
    client: VisionClient,
    client_factory=None,
    limit: int | None = None,
) -> ImageProcessResult:
    import sqlite3
    result = ImageProcessResult()
    con = sqlite3.connect(cfg.db_path)
    con.row_factory = sqlite3.Row
    q = (
        "SELECT i.id, i.article_url, i.src, i.alt, i.section_heading, i.content_hash, d.model_id, d.extraction_version "
        "FROM images i LEFT JOIN image_descriptions d ON d.image_id = i.id "
        "WHERE i.is_active = 1 AND (d.image_id IS NULL OR d.extraction_version < ?) "
        "ORDER BY i.id"
    )
    rows = con.execute(q, (cfg.extraction_version,)).fetchall()
    if limit:
        rows = rows[:limit]
    con.close()

    http_client = client_factory(cfg) if client_factory else httpx.AsyncClient(
        timeout=cfg.request_timeout_seconds, headers={"User-Agent": cfg.user_agent}, follow_redirects=True,
    )
    fetcher = PoliteFetcher(cfg, client=http_client)
    try:
        for row in rows:
            try:
                res = await fetcher.fetch(row["src"])
                if len(res.content) > MAX_IMAGE_BYTES:
                    raise PermanentFetchError(f"image too large: {len(res.content)} bytes")
            except (PermanentFetchError, TransientFetchError) as exc:
                _write(con, int(row["id"]), ImageDescription("", "failed", client.model_id, str(exc)), cfg.extraction_version)
                result.failed += 1
                continue
            desc = client.describe(res.content, context_text=row["alt"] or row["section_heading"])
            _write(con, int(row["id"]), desc, cfg.extraction_version)
            result.processed += 1
            if desc.status == "simulated":
                result.simulated += 1
        return result
    finally:
        await fetcher.aclose()


def _write(con, image_id: int, desc: ImageDescription, extraction_version: int) -> None:
    con.execute(
        "INSERT INTO image_descriptions (image_id, model_id, description, status, uncertainty, extraction_version, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(image_id) DO UPDATE SET model_id=excluded.model_id, description=excluded.description, "
        "status=excluded.status, uncertainty=excluded.uncertainty, extraction_version=excluded.extraction_version, "
        "created_at=excluded.created_at",
        (image_id, desc.model_id, desc.description, desc.status, desc.uncertainty, extraction_version, _now()),
    )
    con.commit()
