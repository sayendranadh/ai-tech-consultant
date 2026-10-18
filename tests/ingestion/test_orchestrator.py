from pathlib import Path

import httpx
import pytest

from task1_knowledge_brain.ingestion.config import IngestionConfig
from task1_knowledge_brain.ingestion.manifest import ManifestStore
from task1_knowledge_brain.ingestion.orchestrator import run_ingestion

FIX = Path(__file__).parent.parent / "fixtures"


def _make_factory(handler):
    def factory(cfg: IngestionConfig) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            headers={"User-Agent": cfg.user_agent},
            timeout=cfg.request_timeout_seconds,
            follow_redirects=True,
        )
    return factory


@pytest.mark.asyncio
async def test_idempotent_second_run(tmp_path):
    cfg = IngestionConfig(
        KB_DB_PATH=tmp_path / "kb.sqlite3",
        KB_MAX_RETRIES=1,
        KB_BACKOFF_BASE_SECONDS=0.001,
        KB_BACKOFF_MAX_SECONDS=0.01,
    )

    async def handler(request):
        url = str(request.url)
        if url.endswith("/sitemap.xml"):
            return httpx.Response(200, content=(FIX / "sitemap_index.xml").read_bytes())
        if url.endswith("sitemap_pages.xml"):
            return httpx.Response(200, content=(FIX / "sitemap_pages.xml").read_bytes())
        if url.endswith("/robots.txt"):
            return httpx.Response(404)
        if "/article/" in url:
            return httpx.Response(200, content=(FIX / "article_a.html").read_bytes())
        return httpx.Response(404)

    factory = _make_factory(handler)

    await run_ingestion(cfg, client_factory=factory)
    store = ManifestStore(cfg.db_path)
    docs_1 = store.count("documents")
    chunks_1 = store.count("chunks")

    report_2 = await run_ingestion(cfg, client_factory=factory)
    docs_2 = store.count("documents")
    chunks_2 = store.count("chunks")

    assert docs_1 > 0
    assert docs_1 == docs_2, "second run must not create new documents"
    assert chunks_1 == chunks_2, "second run must not create new chunks"
    assert report_2.counts["unchanged"] >= 1


@pytest.mark.asyncio
async def test_permanent_failure_isolated(tmp_path):
    cfg = IngestionConfig(
        KB_DB_PATH=tmp_path / "kb.sqlite3",
        KB_MAX_RETRIES=1,
        KB_BACKOFF_BASE_SECONDS=0.001,
        KB_BACKOFF_MAX_SECONDS=0.01,
    )

    async def handler(request):
        url = str(request.url)
        if url.endswith("/sitemap.xml"):
            return httpx.Response(200, content=(FIX / "sitemap_index.xml").read_bytes())
        if url.endswith("sitemap_pages.xml"):
            return httpx.Response(200, content=(FIX / "sitemap_pages.xml").read_bytes())
        if url.endswith("/robots.txt"):
            return httpx.Response(404)
        if url.endswith("/article/b"):
            return httpx.Response(404)
        if "/article/" in url:
            return httpx.Response(200, content=(FIX / "article_a.html").read_bytes())
        return httpx.Response(404)

    factory = _make_factory(handler)
    report = await run_ingestion(cfg, client_factory=factory)

    assert report.counts["failed_permanent"] == 1
    store = ManifestStore(cfg.db_path)
    a = store.get_row("https://support.brilliantdirectories.com/article/a")
    b = store.get_row("https://support.brilliantdirectories.com/article/b")
    assert a is not None and a["processing_status"] == "processed"
    assert b is not None and b["processing_status"] == "failed_permanent"


@pytest.mark.asyncio
async def test_removed_page_deactivates_chunks(tmp_path):
    cfg = IngestionConfig(
        KB_DB_PATH=tmp_path / "kb.sqlite3",
        KB_MAX_RETRIES=1,
        KB_BACKOFF_BASE_SECONDS=0.001,
        KB_BACKOFF_MAX_SECONDS=0.01,
    )
    only_a = b"""<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://support.brilliantdirectories.com/article/a</loc></url></urlset>"""

    # Run 1: two pages
    async def handler1(request):
        url = str(request.url)
        if url.endswith("/sitemap.xml"):
            return httpx.Response(200, content=(FIX / "sitemap_index.xml").read_bytes())
        if url.endswith("sitemap_pages.xml"):
            return httpx.Response(200, content=(FIX / "sitemap_pages.xml").read_bytes())
        if url.endswith("/robots.txt"):
            return httpx.Response(404)
        if "/article/" in url:
            return httpx.Response(200, content=(FIX / "article_a.html").read_bytes())
        return httpx.Response(404)

    await run_ingestion(cfg, client_factory=_make_factory(handler1))
    store = ManifestStore(cfg.db_path)
    assert store.get_row("https://support.brilliantdirectories.com/article/b") is not None

    # Run 2: only page a
    async def handler2(request):
        url = str(request.url)
        if url.endswith("/sitemap.xml"):
            return httpx.Response(200, content=(FIX / "sitemap_index.xml").read_bytes())
        if url.endswith("sitemap_pages.xml"):
            return httpx.Response(200, content=only_a)
        if url.endswith("/robots.txt"):
            return httpx.Response(404)
        if "/article/" in url:
            return httpx.Response(200, content=(FIX / "article_a.html").read_bytes())
        return httpx.Response(404)

    report = await run_ingestion(cfg, client_factory=_make_factory(handler2))

    assert report.counts["removed"] == 1
    store = ManifestStore(cfg.db_path)
    with store._conn() as con:
        active_b = con.execute(
            "SELECT COUNT(*) c FROM chunks WHERE url LIKE '%/article/b' AND is_active=1"
        ).fetchone()["c"]
    b = store.get_row("https://support.brilliantdirectories.com/article/b")
    assert active_b == 0
    assert b is not None and b["processing_status"] == "removed"


@pytest.mark.asyncio
async def test_transient_failure_recorded(tmp_path):
    """Bonus test: one page 503 twice then success; verifies isolation + retry counts."""
    cfg = IngestionConfig(
        KB_DB_PATH=tmp_path / "kb.sqlite3",
        KB_MAX_RETRIES=3,
        KB_BACKOFF_BASE_SECONDS=0.001,
        KB_BACKOFF_MAX_SECONDS=0.01,
    )
    attempts = {"a": 0}

    async def handler(request):
        url = str(request.url)
        if url.endswith("/sitemap.xml"):
            return httpx.Response(200, content=(FIX / "sitemap_index.xml").read_bytes())
        if url.endswith("sitemap_pages.xml"):
            return httpx.Response(200, content=(FIX / "sitemap_pages.xml").read_bytes())
        if url.endswith("/robots.txt"):
            return httpx.Response(404)
        if url.endswith("/article/a"):
            attempts["a"] += 1
            if attempts["a"] < 3:
                return httpx.Response(503)
        if "/article/" in url:
            return httpx.Response(200, content=(FIX / "article_a.html").read_bytes())
        return httpx.Response(404)

    report = await run_ingestion(cfg, client_factory=_make_factory(handler))
    # Page a eventually succeeds; page b fails because we only special-case 404 in other test.
    assert attempts["a"] >= 3
    store = ManifestStore(cfg.db_path)
    a = store.get_row("https://support.brilliantdirectories.com/article/a")
    assert a is not None and a["processing_status"] == "processed"


@pytest.mark.asyncio
async def test_limit_flag_limits_discovery_and_ingestion(tmp_path):
    """`--limit N` must stop discovery after N URLs AND limit ingestion to N.

    Regression test for the bug where a --limit 3 pilot crawl ingested 1240
    documents because the discovery loop fetched every child sitemap before
    applying the limit.
    """
    cfg = IngestionConfig(
        KB_DB_PATH=tmp_path / "kb.sqlite3",
        KB_MAX_RETRIES=1,
        KB_BACKOFF_BASE_SECONDS=0.001,
        KB_BACKOFF_MAX_SECONDS=0.01,
    )

    # Synthesize a sitemap index with 5 child sitemaps, each with 10 URLs.
    children = []
    for i in range(5):
        children.append(f"https://support.brilliantdirectories.com/child-{i}.xml")

    index_xml = (
        '<?xml version="1.0"?>'
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join(f"<sitemap><loc>{c}</loc></sitemap>" for c in children)
        + "</sitemapindex>"
    ).encode()

    child_xmls: dict[str, bytes] = {}
    for i, child in enumerate(children):
        urls = "".join(
            f"<url><loc>https://support.brilliantdirectories.com/article/{i}-{j}</loc></url>"
            for j in range(10)
        )
        child_xmls[child] = (
            '<?xml version="1.0"?>'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            + urls + "</urlset>"
        ).encode()

    # Track which child sitemaps are actually fetched — this proves discovery stopped early.
    fetched_children: list[str] = []

    async def handler(request):
        url = str(request.url)
        if url.endswith("sitemap.xml"):
            return httpx.Response(200, content=index_xml)
        if url.endswith("/robots.txt"):
            return httpx.Response(404)
        if url in child_xmls:
            fetched_children.append(url)
            return httpx.Response(200, content=child_xmls[url])
        if "/article/" in url:
            return httpx.Response(200, content=b"<html><body><h1>A</h1><p>text</p></body></html>")
        return httpx.Response(404)

    def factory(c: IngestionConfig) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            headers={"User-Agent": c.user_agent},
            timeout=c.request_timeout_seconds,
            follow_redirects=True,
        )

    report = await run_ingestion(cfg, limit=3, client_factory=factory)

    # Assert discovery stopped early: NOT all 5 child sitemaps were fetched.
    assert len(fetched_children) < len(children), (
        f"discovery should have stopped early; fetched {len(fetched_children)} of {len(children)} child sitemaps"
    )

    # Assert ingestion was limited: exactly 3 new entries.
    assert report.counts["new"] == 3, report.counts

    # Assert 3 documents in DB (not 50).
    store = ManifestStore(cfg.db_path)
    assert store.count("documents") == 3
