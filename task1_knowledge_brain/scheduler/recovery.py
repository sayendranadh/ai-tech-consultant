"""Recovery: find in_progress rows and re-mark them pending for the next run."""
from __future__ import annotations

import logging

from ..ingestion.config import IngestionConfig
from ..ingestion.manifest import ManifestStore

log = logging.getLogger(__name__)


def recover_interrupted(cfg: IngestionConfig) -> int:
    store = ManifestStore(cfg.db_path)
    urls = store.list_in_progress()
    for url in urls:
        store.mark_status(url, "pending", error="recovered at startup", bump_attempts=False)
    if urls:
        log.info("recovered %d interrupted URLs", len(urls))
    return len(urls)
