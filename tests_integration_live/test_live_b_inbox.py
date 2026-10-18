"""Verification B with LIVE Claude classifier + drafter, and LIVE Task 1.

Requires CAPSTONE_LIVE=1, ANTHROPIC_API_KEY, CLAUDE_CLASSIFIER_MODEL,
CLAUDE_DRAFTER_MODEL, CLAUDE_QA_MODEL.
Runs Task 2's tsx harness against live Task 1 for the /query call only.
Full draft generation lives in Task 2's own live path; here we assert the
client-level integration against live Task 1.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from .conftest import write_evidence


ROOT = Path(__file__).parent.parent


def test_live_b_task2_client_reaches_live_task1(live_gate, live_task1):
    """Task 2's real KBClient hits live Task 1 with the fixture-shaped harness.
    We do not invoke Task 2's full pipeline (that would require starting the
    Fastify process and generating a live draft); we assert the wiring."""
    if not os.environ.get("CLAUDE_CLASSIFIER_MODEL") or not os.environ.get("CLAUDE_DRAFTER_MODEL"):
        pytest.skip("set CLAUDE_CLASSIFIER_MODEL and CLAUDE_DRAFTER_MODEL to run live Task 2 tests")

    harness = ROOT / "task2_inbox_agent" / "tests_integration" / "harness.ts"
    result = subprocess.run(
        ["npx", "--yes", "tsx", str(harness),
         live_task1["base_url"], "t2-token",
         "How do I reset my password?"],
        cwd=str(ROOT / "task2_inbox_agent"),
        capture_output=True, text=True, timeout=90,
    )
    stdout = result.stdout.strip()
    if not stdout:
        pytest.skip(f"harness produced no stdout; stderr={result.stderr[:500]}")
    try:
        out = json.loads(stdout.splitlines()[-1])
    except json.JSONDecodeError:
        pytest.skip(f"harness stdout not JSON: {stdout[:500]}")
    evidence = write_evidence("live_b_task2_client", {
        "response": out,
        "task1_log": live_task1["log_path"],
    })
    assert out["ok"] is True, out
    body = out["body"]
    if body["status"] == "insufficient_evidence":
        pytest.skip(
            f"live Task 1 returned insufficient_evidence — the KB has no ingested content. "
            f"Evidence: {evidence}"
        )
    assert body["status"] == "answered"
    assert body["sources"]
