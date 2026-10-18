"""End-to-end wiring tests: Task 2 and Task 3 call a real Task 1 over HTTP.

Task 1 runs as a subprocess in `KB_QA_CLIENT=fixture` mode. Task 2's real
KBClient (via tsx harness) and Task 3's real HTTPKBClient both hit it.
No live Claude, no live crawl, no fabricated answers.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).parent.parent
HARNESS = ROOT / "task2_inbox_agent" / "tests_integration" / "harness.ts"


def _run_harness(base_url: str, token: str, question: str) -> dict:
    """Invoke Task 2's KBClient via tsx harness. Returns parsed JSON from stdout."""
    result = subprocess.run(
        ["npx", "--yes", "tsx", str(HARNESS), base_url, token, question],
        cwd=str(ROOT / "task2_inbox_agent"),
        capture_output=True,
        text=True,
        timeout=30,
    )
    stdout = result.stdout.strip()
    if not stdout:
        raise AssertionError(f"harness produced no stdout. stderr={result.stderr[:1000]}")
    try:
        return json.loads(stdout.splitlines()[-1])
    except json.JSONDecodeError as exc:
        raise AssertionError(f"harness stdout not JSON. stdout={stdout[:1000]}") from exc


def test_direct_http_query_returns_fixture_answer(task1_process):
    """Verification A wiring: /query in fixture mode returns answer with cited source."""
    r = httpx.post(
        f"{task1_process['base_url']}/query",
        headers={"Authorization": "Bearer t2-token"},
        json={"question": "how do i reset a password"},
        timeout=10.0,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "answered"
    assert body["answer"].startswith("[FIXTURE]")
    assert body["sources"]
    assert body["sources"][0]["chunk_id"] == 1


def test_request_id_echoed(task1_process):
    """RequestIDMiddleware: x-request-id in → x-request-id out."""
    r = httpx.get(
        f"{task1_process['base_url']}/health",
        headers={"x-request-id": "abc-123"},
    )
    assert r.status_code == 200
    assert r.headers.get("x-request-id") == "abc-123"


def test_request_id_generated_when_absent(task1_process):
    r = httpx.get(f"{task1_process['base_url']}/health")
    assert r.status_code == 200
    assert r.headers.get("x-request-id")


def test_task2_kbclient_against_live_task1(task1_process):
    """Verification B wiring: Task 2's real KBClient talks to live Task 1."""
    out = _run_harness(
        task1_process["base_url"],
        task1_process["task2_token"],
        "how do i reset a password",
    )
    assert out["ok"] is True, out
    body = out["body"]
    assert body["status"] == "answered"
    assert body["answer"].startswith("[FIXTURE]")
    assert body["sources"]


def test_task2_kbclient_insufficient_evidence(task1_process):
    """Verification D wiring: unsupported question flows through Task 2's client as insufficient."""
    out = _run_harness(
        task1_process["base_url"],
        task1_process["task2_token"],
        "what is the airspeed velocity of an unladen swallow",
    )
    assert out["ok"] is True, out
    assert out["body"]["status"] == "insufficient_evidence"


def test_task3_httpkbclient_against_live_task1(task1_process):
    """Verification C wiring: Task 3's HTTPKBClient talks to live Task 1."""
    import sys
    sys.path.insert(0, str(ROOT / "task3_meeting_to_scope"))
    from src.kb_client import HTTPKBClient
    client = HTTPKBClient(
        base_url=task1_process["base_url"],
        bearer_token=task1_process["task3_token"],
        timeout_ms=5000,
        max_retries=1,
    )
    resp = client.query("does the product support custom theming")
    assert resp["status"] == "answered"
    assert resp["answer"].startswith("[FIXTURE]")
    assert resp["sources"]


def test_task3_feasibility_heuristic_on_live_answer(task1_process):
    """Verification C deeper wiring: FeasibilityAgent classifies live Task 1 answer."""
    import sys
    sys.path.insert(0, str(ROOT / "task3_meeting_to_scope"))
    from src.feasibility_agent import FeasibilityAgent
    from src.kb_client import HTTPKBClient
    from src.schemas import Requirement, TurnRef
    kb = HTTPKBClient(base_url=task1_process["base_url"], bearer_token=task1_process["task3_token"], timeout_ms=5000, max_retries=1)
    agent = FeasibilityAgent(kb=kb)
    req = Requirement(
        requirement_id="REQ-TEST-1", project_id="project_website",
        description="support custom theming",
        source_meeting=1,
        source_refs=[TurnRef(transcript_id="t", turn_id="turn-001", speaker="s", quote="q")],
        provenance="client_stated",
    )
    check = agent.check(req)
    assert check.classification == "existing_configuration", check
    assert check.status == "checked"
    assert check.evidence_chunk_ids


def test_task3_feasibility_insufficient_evidence_when_no_fixture(task1_process):
    """Verification C + D: Task 3 FeasibilityAgent returns needs_clarification
    when Task 1 has no fixture answer (insufficient evidence flows through)."""
    import sys
    sys.path.insert(0, str(ROOT / "task3_meeting_to_scope"))
    from src.feasibility_agent import FeasibilityAgent
    from src.kb_client import HTTPKBClient
    from src.schemas import Requirement, TurnRef
    kb = HTTPKBClient(base_url=task1_process["base_url"], bearer_token=task1_process["task3_token"], timeout_ms=5000, max_retries=1)
    agent = FeasibilityAgent(kb=kb)
    req = Requirement(
        requirement_id="REQ-TEST-NOFIX", project_id="project_website",
        description="a product feature with no fixture answer",
        source_meeting=1,
        source_refs=[TurnRef(transcript_id="t", turn_id="turn-001", speaker="s", quote="q")],
        provenance="client_stated",
    )
    check = agent.check(req)
    assert check.classification == "needs_clarification", check
    assert check.status == "escalated", check
    assert check.kb_status == "insufficient_evidence", check
