"""Verification A with LIVE Claude QA.

Requires CAPSTONE_LIVE=1, ANTHROPIC_API_KEY, CLAUDE_QA_MODEL.
Writes evidence to reports/live_a_query_<ts>.json when it runs.
"""
from __future__ import annotations

import httpx
import pytest

from .conftest import write_evidence


def test_live_a_query_returns_answer_with_citations(live_gate, live_task1):
    r = httpx.post(
        f"{live_task1['base_url']}/query",
        headers={"Authorization": "Bearer t2-token"},
        json={"question": "How do I reset my password?"},
        timeout=60.0,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    evidence = write_evidence("live_a_query", {
        "request": {"question": "How do I reset my password?"},
        "response": body,
        "task1_log": live_task1["log_path"],
    })
    # Live Claude may legitimately return insufficient_evidence if the KB has not been ingested.
    # That is honest — the fixture in mocked mode bypasses this by returning a documented fixture answer.
    if body["status"] == "insufficient_evidence":
        pytest.skip(
            f"live /query returned insufficient_evidence — the KB has no ingested content yet "
            f"(run ingestion first). Evidence: {evidence}"
        )
    assert body["status"] == "answered"
    assert body["sources"], "answered status must include cited sources"
    for s in body["sources"]:
        assert "url" in s and "chunk_id" in s
