"""Chunk articles along heading boundaries; keep steps/prereqs with content."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from .parser import ParsedArticle


@dataclass(frozen=True)
class Chunk:
    index: int
    text: str
    section_heading: str | None
    content_hash: str


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def chunk_article(article: ParsedArticle, max_chars: int = 1500, overlap_chars: int = 150) -> list[Chunk]:
    """
    Heading-aware chunking. Splits body_text on lines that exactly match a known
    heading text. Steps (lines beginning with list markers) are kept with their
    preceding heading section. No overlap across heading boundaries.
    """
    if not article.body_text.strip():
        return []

    heading_texts = {h.text for h in article.headings}
    lines = article.body_text.splitlines()

    sections: list[tuple[str | None, list[str]]] = []
    current_heading: str | None = None
    buffer: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped in heading_texts:
            if buffer:
                sections.append((current_heading, buffer))
                buffer = []
            current_heading = stripped
            continue
        buffer.append(line)
    if buffer:
        sections.append((current_heading, buffer))

    chunks: list[Chunk] = []
    idx = 0
    for heading, buffered_lines in sections:
        text = "\n".join(buffered_lines).strip()
        if not text:
            continue
        if len(text) <= max_chars:
            chunks.append(Chunk(index=idx, text=text, section_heading=heading, content_hash=_hash(text)))
            idx += 1
            continue
        # Split long sections with overlap.
        start = 0
        while start < len(text):
            end = min(start + max_chars, len(text))
            piece = text[start:end]
            chunks.append(Chunk(index=idx, text=piece, section_heading=heading, content_hash=_hash(piece)))
            idx += 1
            if end == len(text):
                break
            start = max(end - overlap_chars, start + 1)
    return chunks
