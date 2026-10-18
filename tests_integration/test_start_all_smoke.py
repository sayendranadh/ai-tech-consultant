"""Smoke test: scripts/start_all.sh starts all three services and they reach /health.

Marked with @pytest.mark.slow because it starts three subprocesses and can take 60s.
Skipped by default unless RUN_SMOKE=1 is set in the environment (to avoid
breaking fast local test runs).
"""
from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
import pytest


ROOT = Path(__file__).parent.parent
SCRIPT = ROOT / "scripts" / "start_all.sh"


@pytest.mark.skipif(
    os.environ.get("RUN_SMOKE", "0") != "1",
    reason="set RUN_SMOKE=1 to run the start_all.sh smoke test (starts 3 subprocesses)",
)
def test_start_all_script_brings_up_three_services():
    if not SCRIPT.exists():
        pytest.skip("scripts/start_all.sh not present")
    if not (ROOT / "task2_inbox_agent" / "node_modules").exists():
        pytest.skip("task2 node_modules not installed")

    # Isolate: use temporary DB paths so we don't contend with existing files.
    with tempfile.TemporaryDirectory() as td:
        env = {
            **os.environ,
            "KB_DB_PATH": f"{td}/t1.sqlite3",
            "KB_QA_CLIENT": "fixture",
            "KB_API_TOKEN_TASK2": "t2-token",
            "KB_API_TOKEN_TASK3": "t3-token",
            "KB_API_TOKEN_ADMIN": "admin-token",
            "KB_SERVICE_PORT": "8000",
            "T2_DB_PATH": f"{td}/t2.sqlite3",
            "T2_PORT": "8100",
            "KB_BASE_URL": "http://127.0.0.1:8000",
            "KB_BEARER_TOKEN": "t2-token",
            "T3_DB_PATH": f"{td}/t3.sqlite3",
            "T3_PORT": "8200",
            "PYTHONPATH": str(ROOT),
        }
        # start_all.sh uses bash; run in its own process group so we can kill it cleanly.
        log = Path(td) / "start_all.log"
        proc = subprocess.Popen(
            ["bash", str(SCRIPT)],
            cwd=str(ROOT),
            env=env,
            stdout=log.open("w"),
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            healthy = _wait_all_healthy(deadline=time.monotonic() + 90.0)
            assert healthy, f"not all services healthy in 90s. Log: {log.read_text()[:2000]}"
        finally:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass


def _wait_all_healthy(deadline: float) -> bool:
    urls = [
        "http://127.0.0.1:8000/health",
        "http://127.0.0.1:8100/health",
        "http://127.0.0.1:8200/health",
    ]
    while time.monotonic() < deadline:
        results = []
        for u in urls:
            try:
                r = httpx.get(u, timeout=1.0)
                results.append(r.status_code == 200)
            except Exception:
                results.append(False)
        if all(results):
            return True
        time.sleep(1.0)
    return False
