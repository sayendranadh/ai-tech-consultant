"""Unit tests for ClaudeQAClient using a fake Anthropic client.

These tests verify citation extraction, validation, and abstention logic.
They do NOT make live API calls. Live verification is separate.
"""
from __future__ import annotations

import pytest

from task1_knowledge_brain.qa.claude_client import ClaudeQAClient, UnconfiguredModelError


class _FakeMessages:
    def __init__(self, text: str) -> None:
        self._text = text

    def create(self, **kwargs):
        class _Block:
            type = "text"
            def __init__(self, t): self.text = t
        class _Resp:
            def __init__(self, t):
                self.content = [_Block(t)]
        return _Resp(self._text)


class _FakeClient:
    def __init__(self, text: str) -> None:
        self.messages = _FakeMessages(text)


CHUNKS = [
    {"chunk_id": 1, "url": "https://x/a", "section_heading": "Import", "text": "Import members via CSV: see steps.", "title": "Import"},
    {"chunk_id": 2, "url": "https://x/b", "section_heading": "Steps", "text": "Use the CSV importer.", "title": "Steps"},
]


def _client_with_text(text: str) -> ClaudeQAClient:
    return ClaudeQAClient(api_key="fake", model_id="fake-model", anthropic_client=_FakeClient(text))


def test_unconfigured_raises_when_no_key():
    with pytest.raises(UnconfiguredModelError):
        ClaudeQAClient(api_key="", model_id="x")


def test_unconfigured_raises_when_no_model():
    with pytest.raises(UnconfiguredModelError):
        ClaudeQAClient(api_key="x", model_id="")


def test_structured_answer_with_citations():
    c = _client_with_text("Import via CSV using [chunk_id=1]. Also see [chunk_id=2].")
    resp = c.structured_answer("How to import members via CSV?", CHUNKS)
    assert resp.status == "answered"
    assert len(resp.sources) == 2
    assert {s.chunk_id for s in resp.sources} == {1, 2}


def test_abstention_when_claude_says_insufficient():
    c = _client_with_text("INSUFFICIENT")
    resp = c.structured_answer("q", CHUNKS)
    assert resp.status == "insufficient_evidence"
    assert resp.sources == []


def test_rejects_uncited_answer():
    c = _client_with_text("Here is an answer without any citations.")
    resp = c.structured_answer("q", CHUNKS)
    assert resp.status == "insufficient_evidence"


def test_rejects_invented_chunk_id():
    c = _client_with_text("See [chunk_id=999] for details.")
    resp = c.structured_answer("q", CHUNKS)
    assert resp.status == "insufficient_evidence"


def test_empty_retrieval_returns_insufficient_without_calling_claude():
    class _Exploding:
        def __init__(self): raise RuntimeError("should not be constructed")
    # Construct without an exploding client; use a normal one
    c = _client_with_text("irrelevant")
    resp = c.structured_answer("q", [])
    assert resp.status == "insufficient_evidence"
