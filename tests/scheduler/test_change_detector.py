from datetime import datetime, timezone

from task1_knowledge_brain.ingestion.config import IngestionConfig
from task1_knowledge_brain.ingestion.manifest import ManifestStore
from task1_knowledge_brain.ingestion.sitemap_parser import SitemapEntry
from task1_knowledge_brain.scheduler.change_detector import classify


def test_classify_new_updated_unchanged_removed(tmp_path):
    cfg = IngestionConfig(KB_DB_PATH=tmp_path / "kb.sqlite3", KB_EXTRACTION_VERSION=1)
    store = ManifestStore(cfg.db_path)

    # Seed three URLs: one unchanged, one removed (in manifest but not sitemap).
    store.upsert_pending("https://x/a", "2025-01-01T00:00:00+00:00")
    store.mark_processed("https://x/a", "hashA", 1)
    store.upsert_pending("https://x/removed", "2025-01-01T00:00:00+00:00")
    store.mark_processed("https://x/removed", "hashR", 1)

    sitemap = [
        SitemapEntry(url="https://x/a", lastmod=datetime(2025, 1, 1, tzinfo=timezone.utc)),
        SitemapEntry(url="https://x/b", lastmod=None),
        SitemapEntry(url="https://x/c", lastmod=None),
    ]
    # 'b' exists with different lastmod — updated
    store.upsert_pending("https://x/b", "2024-12-01T00:00:00+00:00")
    store.mark_processed("https://x/b", "hashB", 1)

    cs = classify(sitemap, store, extraction_version=1)
    new_urls = {e.url for e in cs.new}
    updated_urls = {e.url for e in cs.updated}
    unchanged_urls = {e.url for e in cs.unchanged}

    assert "https://x/c" in new_urls
    assert "https://x/b" in updated_urls
    assert "https://x/a" in unchanged_urls
    assert "https://x/removed" in cs.removed_urls
