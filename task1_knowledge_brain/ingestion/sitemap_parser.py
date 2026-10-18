"""Parse sitemaps and sitemap indexes. Pure functions, no I/O."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

_NS_TAG_PREFIX = "{http://www.sitemaps.org/schemas/sitemap/0.9}"


class SitemapError(ValueError):
    pass


@dataclass(frozen=True)
class SitemapEntry:
    url: str
    lastmod: datetime | None


@dataclass(frozen=True)
class SitemapIndexEntry:
    loc: str
    lastmod: datetime | None


@dataclass(frozen=True)
class ParsedSitemap:
    kind: str
    urls: list[SitemapEntry]
    children: list[SitemapIndexEntry]


def _parse_lastmod(value: str | None) -> datetime | None:
    if not value:
        return None
    v = value.strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            return datetime.strptime(v.replace("Z", "+0000"), fmt)
        except ValueError:
            continue
    return None


def _find_child_text(parent: ET.Element, tag: str) -> str | None:
    child = parent.find(f"{_NS_TAG_PREFIX}{tag}")
    if child is None:
        child = parent.find(tag)
    if child is None:
        return None
    text = (child.text or "").strip()
    return text or None


def _root_tag_name(root: ET.Element) -> str:
    if root.tag.startswith("{"):
        return root.tag.split("}", 1)[-1]
    return root.tag


def parse_sitemap_xml(xml_bytes: bytes) -> ParsedSitemap:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise SitemapError(f"malformed sitemap XML: {exc}") from exc

    tag = _root_tag_name(root)

    if tag == "urlset":
        urls: list[SitemapEntry] = []
        candidates = list(root.findall(f"{_NS_TAG_PREFIX}url")) or list(root.findall("url"))
        for url_el in candidates:
            loc = _find_child_text(url_el, "loc")
            if not loc:
                continue
            urls.append(SitemapEntry(url=loc, lastmod=_parse_lastmod(_find_child_text(url_el, "lastmod"))))
        return ParsedSitemap(kind="urlset", urls=urls, children=[])

    if tag == "sitemapindex":
        children: list[SitemapIndexEntry] = []
        candidates = list(root.findall(f"{_NS_TAG_PREFIX}sitemap")) or list(root.findall("sitemap"))
        for sm_el in candidates:
            loc = _find_child_text(sm_el, "loc")
            if not loc:
                continue
            children.append(SitemapIndexEntry(loc=loc, lastmod=_parse_lastmod(_find_child_text(sm_el, "lastmod"))))
        # --- FIX: return the collected children, not an empty list ---
        return ParsedSitemap(kind="sitemapindex", urls=[], children=children)

    raise SitemapError(f"unexpected sitemap root element: {tag}")


def is_allowed_url(url: str, allowed_domain: str) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme not in ("https", "http"):
        return False
    host = (parsed.hostname or "").lower()
    allowed = allowed_domain.lower().lstrip(".")
    return host == allowed or host.endswith("." + allowed)


def dedupe_urls(entries: list[SitemapEntry]) -> list[SitemapEntry]:
    seen: set[str] = set()
    out: list[SitemapEntry] = []
    for e in entries:
        if e.url in seen:
            continue
        seen.add(e.url)
        out.append(e)
    return out
