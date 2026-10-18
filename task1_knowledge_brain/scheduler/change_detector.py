"""Classify sitemap entries against the manifest: new / updated / unchanged / removed."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..ingestion.manifest import ManifestStore
from ..ingestion.sitemap_parser import SitemapEntry


@dataclass
class ChangeSet:
    new: list[SitemapEntry] = field(default_factory=list)
    updated: list[SitemapEntry] = field(default_factory=list)   # lastmod OR hash differs
    unchanged: list[SitemapEntry] = field(default_factory=list)
    removed_urls: list[str] = field(default_factory=list)


def classify(
    entries: list[SitemapEntry],
    store: ManifestStore,
    extraction_version: int,
) -> ChangeSet:
    """
    Sitemap entries drive new/updated/unchanged classification.
    Manifest URLs not in sitemap → removed.
    Hash check is deferred to ingestion (network cost); here we use lastmod
    + extraction_version. Ingestion re-checks hash and short-circuits to
    'unchanged' if hash matches (see orchestrator.process).
    """
    cs = ChangeSet()
    sitemap_urls: set[str] = set()
    for entry in entries:
        sitemap_urls.add(entry.url)
        existing = store.get(entry.url)
        if existing is None or existing["processing_status"] == "removed":
            cs.new.append(entry)
            continue
        lastmod_str = entry.lastmod.isoformat() if entry.lastmod else None
        same_lastmod = lastmod_str and existing["sitemap_lastmod"] == lastmod_str
        same_version = existing["extraction_version"] == extraction_version
        if same_lastmod and same_version:
            cs.unchanged.append(entry)
        else:
            cs.updated.append(entry)

    for url in store.list_active_urls():
        if url not in sitemap_urls:
            cs.removed_urls.append(url)

    return cs
