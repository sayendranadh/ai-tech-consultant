"""Deterministic out-of-scope detection via phrase markers."""
from __future__ import annotations

MARKERS = (
    "out of scope",
    "not in scope",
    "separate phase",
    "we'll do that later",
    "later phase",
    "not for this project",
)


def is_out_of_scope(text: str) -> bool:
    t = text.lower()
    return any(m in t for m in MARKERS)
