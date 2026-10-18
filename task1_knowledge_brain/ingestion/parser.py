"""Extract structured article content from HTML."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

import trafilatura
from bs4 import BeautifulSoup

NAV_SELECTORS = [
    "nav", "header nav", "footer", "aside",
    ".breadcrumb", ".breadcrumbs", ".sidebar", ".menu", ".navbar",
    "[role='navigation']", "[role='banner']", "[role='contentinfo']",
]


@dataclass
class Heading:
    level: int
    text: str


@dataclass
class ImageRef:
    src: str
    alt: str | None
    section_heading: str | None


@dataclass
class ParsedArticle:
    title: str | None
    body_text: str
    headings: list[Heading] = field(default_factory=list)
    lists: list[list[str]] = field(default_factory=list)
    tables: list[list[list[str]]] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)
    images: list[ImageRef] = field(default_factory=list)
    canonical_url: str | None = None
    content_hash: str = ""


def _strip_boilerplate(soup: BeautifulSoup) -> None:
    for sel in NAV_SELECTORS:
        for tag in soup.select(sel):
            tag.decompose()


def _extract_headings(soup: BeautifulSoup) -> list[Heading]:
    out: list[Heading] = []
    for tag in soup.find_all(re.compile(r"^h[1-6]$")):
        text = " ".join(tag.get_text(" ", strip=True).split())
        if text:
            out.append(Heading(level=int(tag.name[1]), text=text))
    return out


def _section_for(img_tag, headings: list[Heading]) -> str | None:
    """Return the nearest preceding heading text, using DOM order."""
    for prev in img_tag.find_all_previous(re.compile(r"^h[1-6]$")):
        text = " ".join(prev.get_text(" ", strip=True).split())
        if text:
            return text
    return headings[0].text if headings else None


def _extract_images(soup: BeautifulSoup, headings: list[Heading], page_url: str) -> list[ImageRef]:
    out: list[ImageRef] = []
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src")
        if not src:
            continue
        # Resolve relative URLs against page URL minimally; full resolution done in storage.
        from urllib.parse import urljoin
        src_abs = urljoin(page_url, src.strip())
        out.append(ImageRef(src=src_abs, alt=(img.get("alt") or None), section_heading=_section_for(img, headings)))
    return out


def _extract_lists(soup: BeautifulSoup) -> list[list[str]]:
    out: list[list[str]] = []
    for lst in soup.find_all(["ul", "ol"]):
        items = [" ".join(li.get_text(" ", strip=True).split()) for li in lst.find_all("li", recursive=False)]
        items = [i for i in items if i]
        if items:
            out.append(items)
    return out


def _extract_tables(soup: BeautifulSoup) -> list[list[list[str]]]:
    out: list[list[list[str]]] = []
    for table in soup.find_all("table"):
        rows: list[list[str]] = []
        for tr in table.find_all("tr"):
            cells = [" ".join(c.get_text(" ", strip=True).split()) for c in tr.find_all(["th", "td"])]
            if cells:
                rows.append(cells)
        if rows:
            out.append(rows)
    return out


def _extract_steps(body_text: str) -> list[str]:
    """Heuristic: lines that start with 1., 2., Step N, or - bullet."""
    steps: list[str] = []
    for line in body_text.splitlines():
        s = line.strip()
        if not s:
            continue
        if re.match(r"^(\d+[\.\)]|Step\s+\d+[:\.]?)\s+\S", s, re.IGNORECASE) or s.startswith("- "):
            steps.append(s)
    return steps


def parse_article(html: bytes | str, page_url: str) -> ParsedArticle:
    if isinstance(html, bytes):
        html_str = html.decode("utf-8", errors="replace")
    else:
        html_str = html

    soup = BeautifulSoup(html_str, "lxml")

    canonical_tag = soup.find("link", rel=lambda v: v and "canonical" in v)
    canonical_url = canonical_tag.get("href") if canonical_tag else None

    title_tag = soup.find("title")
    h1_tag = soup.find("h1")
    title = (h1_tag.get_text(" ", strip=True) if h1_tag else None) or (title_tag.get_text(" ", strip=True) if title_tag else None)

    _strip_boilerplate(soup)
    headings = _extract_headings(soup)

    body_text = trafilatura.extract(
        html_str,
        include_tables=True,
        include_links=False,
        include_images=False,
        favor_precision=True,
    ) or ""

    images = _extract_images(soup, headings, page_url)
    lists = _extract_lists(soup)
    tables = _extract_tables(soup)
    steps = _extract_steps(body_text)

    content_hash = hashlib.sha256(body_text.encode("utf-8")).hexdigest()

    return ParsedArticle(
        title=title,
        body_text=body_text,
        headings=headings,
        lists=lists,
        tables=tables,
        steps=steps,
        images=images,
        canonical_url=canonical_url,
        content_hash=content_hash,
    )
