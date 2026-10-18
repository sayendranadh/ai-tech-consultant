"""Wire sitemap → fetch → parse → manifest. Idempotent. Resume-safe."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx

from .chunker import chunk_article
from .config import IngestionConfig
from .fetcher import PermanentFetchError, PoliteFetcher, TransientFetchError, fetch_robots, robots_allows
from .manifest import ManifestStore
from .parser import parse_article
from .sitemap_parser import SitemapEntry, SitemapError, dedupe_urls, is_allowed_url, parse_sitemap_xml

log = logging.getLogger(__name__)

ClientFactory = "Callable[[IngestionConfig], httpx.AsyncClient]"


@dataclass
class RunReport:
    started_at: str
    finished_at: str = ""
    counts: dict[str, int] = field(default_factory=lambda: {
        "new": 0, "updated": 0, "unchanged": 0, "removed": 0,
        "failed_permanent": 0, "failed_transient": 0, "recovered": 0,
    })
    errors: list[dict] = field(default_factory=list)


async def _collect_sitemap_entries(
    fetcher: PoliteFetcher,
    sitemap_url: str,
    allowed_domain: str,
    limit: int | None,
    robots_txt: str | None,
    user_agent: str,
) -> list[SitemapEntry]:
    seen_indexes: set[str] = set()
    queue: list[str] = [sitemap_url]
    collected: list[SitemapEntry] = []
    while queue:
        # Pilot mode: stop fetching sitemaps as soon as we have enough URLs.
        # Without this check, a sitemap *index* forces us to fetch every child
        # sitemap before collecting, so a --limit 3 pilot crawl ingests the
        # entire site.
        if limit is not None and len(collected) >= limit:
            break
        current = queue.pop(0)
        if current in seen_indexes:
            continue
        seen_indexes.add(current)
        path = urlparse(current).path or "/"
        if not robots_allows(robots_txt, path, user_agent):
            log.warning("robots.txt disallows sitemap path %s; skipping", current)
            continue
        try:
            res = await fetcher.fetch(current)
        except (PermanentFetchError, TransientFetchError) as exc:
            raise SitemapError(f"failed to fetch sitemap {current}: {exc}") from exc
        try:
            parsed = parse_sitemap_xml(res.content)
        except SitemapError:
            if current == sitemap_url:
                raise
            log.warning("child sitemap unparseable, continuing: %s", current)
            continue
        if parsed.kind == "sitemapindex":
            for child in parsed.children:
                if child.loc not in seen_indexes:
                    queue.append(child.loc)
        else:
            collected.extend(parsed.urls)
            if limit is not None and len(collected) >= limit:
                break
    return dedupe_urls(collected)


async def run_ingestion(
    cfg: IngestionConfig,
    limit: int | None = None,
    dry_run: bool = False,
    client_factory=None,
) -> RunReport:
    report = RunReport(started_at=datetime.now(timezone.utc).isoformat())
    store = ManifestStore(cfg.db_path)
    client = client_factory(cfg) if client_factory else None
    fetcher = PoliteFetcher(cfg, client=client)
    try:
        robots_txt = await fetch_robots(fetcher, cfg.sitemap_url)
        entries = await _collect_sitemap_entries(fetcher, cfg.sitemap_url, cfg.source_domain, limit, robots_txt, cfg.user_agent)

        # Recover interrupted rows.
        for url in store.list_in_progress():
            store.mark_status(url, "pending", error="recovered from interrupted run", bump_attempts=False)
            report.counts["recovered"] += 1

        sitemap_urls = {e.url for e in entries}

        # Removals: manifest URLs not present in this sitemap.
        for url in store.list_active_urls():
            if url not in sitemap_urls:
                if not dry_run:
                    store.mark_removed(url)
                report.counts["removed"] += 1

        sem = asyncio.Semaphore(cfg.concurrency)

        async def process(entry: SitemapEntry) -> None:
            async with sem:
                existing = store.get(entry.url)
                lastmod_str = entry.lastmod.isoformat() if entry.lastmod else None

                if (
                    existing
                    and existing["content_hash"]
                    and lastmod_str
                    and existing["sitemap_lastmod"] == lastmod_str
                    and existing["extraction_version"] == cfg.extraction_version
                ):
                    report.counts["unchanged"] += 1
                    return

                if not is_allowed_url(entry.url, cfg.source_domain):
                    report.counts["failed_permanent"] += 1
                    report.errors.append({"url": entry.url, "code": "disallowed_domain", "retryable": False})
                    return

                path = urlparse(entry.url).path or "/"
                if not robots_allows(robots_txt, path, cfg.user_agent):
                    report.counts["failed_permanent"] += 1
                    report.errors.append({"url": entry.url, "code": "robots_disallow", "retryable": False})
                    return

                if dry_run:
                    report.counts["new" if not existing else "updated"] += 1
                    return

                store.upsert_pending(entry.url, lastmod_str)
                store.mark_status(entry.url, "in_progress")

                try:
                    res = await fetcher.fetch(entry.url)
                except PermanentFetchError as exc:
                    store.mark_status(entry.url, "failed_permanent", error=str(exc), bump_attempts=True)
                    report.counts["failed_permanent"] += 1
                    report.errors.append({"url": entry.url, "code": "permanent_fetch", "message": str(exc), "retryable": False})
                    return
                except TransientFetchError as exc:
                    store.mark_status(entry.url, "failed_transient", error=str(exc), bump_attempts=True)
                    report.counts["failed_transient"] += 1
                    report.errors.append({"url": entry.url, "code": "transient_fetch", "message": str(exc), "retryable": True})
                    return

                article = parse_article(res.content, entry.url)
                if (
                    existing
                    and existing["content_hash"] == article.content_hash
                    and existing["extraction_version"] == cfg.extraction_version
                ):
                    store.mark_processed(entry.url, article.content_hash, cfg.extraction_version)
                    report.counts["unchanged"] += 1
                    return

                doc_id = store.write_document(entry.url, article.title, article.body_text, article.canonical_url, article.content_hash)
                chunks = chunk_article(article)
                store.write_chunks(doc_id, entry.url, [(c.index, c.text, c.section_heading, c.content_hash) for c in chunks])
                store.deactivate_stale_chunks(entry.url, keep_document_id=doc_id)
                store.write_images(entry.url, [(i.src, i.alt, i.section_heading, "pending") for i in article.images])
                store.mark_processed(entry.url, article.content_hash, cfg.extraction_version)

                if existing and existing["content_hash"]:
                    report.counts["updated"] += 1
                else:
                    report.counts["new"] += 1

        # Pilot mode: never process more than `limit` URLs, even if discovery
        # over-collected from child sitemaps.
        if limit is not None:
            entries = entries[:limit]
        await asyncio.gather(*(process(e) for e in entries))
        report.finished_at = datetime.now(timezone.utc).isoformat()
        return report
    finally:
        await fetcher.aclose()
