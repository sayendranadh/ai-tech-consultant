from pathlib import Path

import pytest

from task1_knowledge_brain.ingestion.sitemap_parser import (
    SitemapError,
    dedupe_urls,
    is_allowed_url,
    parse_sitemap_xml,
)

FIX = Path(__file__).parent.parent / "fixtures"


def test_parse_urlset():
    parsed = parse_sitemap_xml((FIX / "sitemap_pages.xml").read_bytes())
    assert parsed.kind == "urlset"
    assert len(parsed.urls) == 2
    assert parsed.urls[0].url.endswith("/article/a")
    assert parsed.urls[0].lastmod is not None
    assert parsed.urls[1].lastmod is None


def test_parse_index():
    parsed = parse_sitemap_xml((FIX / "sitemap_index.xml").read_bytes())
    assert parsed.kind == "sitemapindex"
    assert len(parsed.children) == 1
    assert parsed.children[0].loc.endswith("sitemap_pages.xml")


def test_malformed_xml_raises():
    with pytest.raises(SitemapError):
        parse_sitemap_xml((FIX / "sitemap_malformed.xml").read_bytes())


def test_dedupe_preserves_order():
    parsed = parse_sitemap_xml((FIX / "sitemap_pages.xml").read_bytes())
    doubled = parsed.urls + parsed.urls
    deduped = dedupe_urls(doubled)
    assert len(deduped) == 2
    assert deduped[0].url == parsed.urls[0].url


def test_domain_allowlist():
    assert is_allowed_url("https://support.brilliantdirectories.com/a", "support.brilliantdirectories.com")
    assert not is_allowed_url("https://evil.example.com/a", "support.brilliantdirectories.com")
    assert not is_allowed_url("ftp://support.brilliantdirectories.com/a", "support.brilliantdirectories.com")
