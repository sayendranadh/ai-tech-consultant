"""Deterministic unit tests for ClaudeExtractor using a fake anthropic client.

These tests verify the parsing, validation, and error handling logic without
making any API calls. Live verification is in tests_integration_live/.
"""
from __future__ import annotations

import json

import pytest

from src.extractor.base import UnconfiguredModelError
from src.extractor.claude import ClaudeExtractor
from src.ingestion.chunker import Chunk
from src.schemas import TranscriptTurn


class _FakeBlock:
    type = "text"
    def __init__(self, text: str) -> None:
        self.text = text


class _FakeMessages:
    def __init__(self, response_text: str) -> None:
        self._text = response_text
        self.last_call: dict | None = None

    def create(self, **kwargs):
        self.last_call = kwargs
        class _Resp:
            def __init__(self, text: str):
                self.content = [_FakeBlock(text)]
        return _Resp(self._text)


class _FakeAnthropicClient:
    def __init__(self, response_text: str) -> None:
        self.messages = _FakeMessages(response_text)


def _chunk() -> Chunk:
    return Chunk(
        chunk_id="meeting_1-chunk-1",
        transcript_id="meeting_1",
        turns=[
            TranscriptTurn(turn_id="turn-001", speaker="Alice", timestamp="00:00", text="We need a homepage redesign."),
            TranscriptTurn(turn_id="turn-002", speaker="Bob", timestamp="00:30", text="And a contact form."),
        ],
        overlap_turns=[],
    )


def test_unconfigured_raises_when_no_key():
    with pytest.raises(UnconfiguredModelError):
        ClaudeExtractor(api_key="", model_id="x", prompt_version="v1")


def test_unconfigured_raises_when_no_model():
    with pytest.raises(UnconfiguredModelError):
        ClaudeExtractor(api_key="x", model_id="", prompt_version="v1")


def test_parses_valid_records():
    response = json.dumps({"records": [
        {"record_kind": "requirement", "text": "Redesign the homepage",
         "turn_ids": ["turn-001"], "quotes": ["We need a homepage redesign."], "confidence": "high"},
        {"record_kind": "requirement", "text": "Add a contact form",
         "turn_ids": ["turn-002"], "quotes": ["And a contact form."], "confidence": "high"},
    ]})
    client = _FakeAnthropicClient(response)
    ex = ClaudeExtractor(api_key="x", model_id="claude-haiku-5-5", prompt_version="v1", anthropic_client=client)
    records = ex.extract(_chunk())
    assert len(records) == 2
    assert all(r.provenance == "model_inferred" for r in records)
    assert all(len(r.source_refs) >= 1 for r in records)
    assert records[0].source_refs[0].turn_id == "turn-001"


def test_drops_record_with_fabricated_turn_id():
    response = json.dumps({"records": [
        {"record_kind": "requirement", "text": "Fabricated",
         "turn_ids": ["turn-999"], "quotes": ["Fabricated"], "confidence": "high"},
    ]})
    client = _FakeAnthropicClient(response)
    ex = ClaudeExtractor(api_key="x", model_id="claude-haiku-5-5", prompt_version="v1", anthropic_client=client)
    records = ex.extract(_chunk())
    assert records == []


def test_drops_record_with_invalid_quote():
    response = json.dumps({"records": [
        {"record_kind": "requirement", "text": "R",
         "turn_ids": ["turn-001"], "quotes": ["This is not in the turn"], "confidence": "high"},
    ]})
    client = _FakeAnthropicClient(response)
    ex = ClaudeExtractor(api_key="x", model_id="claude-haiku-5-5", prompt_version="v1", anthropic_client=client)
    records = ex.extract(_chunk())
    assert records == []


def test_returns_empty_on_unparseable_response():
    client = _FakeAnthropicClient("Not JSON at all")
    ex = ClaudeExtractor(api_key="x", model_id="claude-haiku-5-5", prompt_version="v1", anthropic_client=client)
    assert ex.extract(_chunk()) == []


def test_returns_empty_on_empty_records_list():
    client = _FakeAnthropicClient(json.dumps({"records": []}))
    ex = ClaudeExtractor(api_key="x", model_id="claude-haiku-5-5", prompt_version="v1", anthropic_client=client)
    assert ex.extract(_chunk()) == []


def test_strips_markdown_code_fences():
    inner = json.dumps({"records": [
        {"record_kind": "decision", "text": "D",
         "turn_ids": ["turn-001"], "quotes": ["We need a homepage redesign."], "confidence": "medium"},
    ]})
    fenced = "```json\n" + inner + "\n```"
    client = _FakeAnthropicClient(fenced)
    ex = ClaudeExtractor(api_key="x", model_id="claude-haiku-5-5", prompt_version="v1", anthropic_client=client)
    records = ex.extract(_chunk())
    assert len(records) == 1
    assert records[0].record_kind == "decision"


def test_extracted_records_carry_model_id():
    """Live extractor records must carry the model_id that produced them."""
    import json as _json
    response = _json.dumps({"records": [
        {"record_kind": "requirement", "text": "Redesign the homepage",
         "turn_ids": ["turn-001"], "quotes": ["We need a homepage redesign."], "confidence": "high"},
    ]})
    client = _FakeAnthropicClient(response)
    ex = ClaudeExtractor(api_key="x", model_id="claude-haiku-5-5", prompt_version="v1", anthropic_client=client)
    records = ex.extract(_chunk())
    assert len(records) == 1
    assert records[0].model_id == "claude-haiku-5-5"
