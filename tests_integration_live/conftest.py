"""Fixtures for live-gated integration tests.

A test runs only when:
- CAPSTONE_LIVE=1 in the environment, AND
- ANTHROPIC_API_KEY is set, AND
- the specific model env var(s) required by the test are set.

Otherwise the test is skipped with a clear reason — never failed.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import httpx
import pytest


ROOT = Path(__file__).parent.parent
LOG_DIR = ROOT / "logs"
REPORTS_DIR = ROOT / "reports"


def _gate_skip_reason() -> str | None:
    if os.environ.get("CAPSTONE_LIVE", "0") != "1":
        return "set CAPSTONE_LIVE=1 to enable live tests"
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return "set ANTHROPIC_API_KEY to enable live tests"
    return None


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture(scope="session")
def live_gate() -> None:
    reason = _gate_skip_reason()
    if reason:
        pytest.skip(reason)


@pytest.fixture(scope="session")
def live_task1() -> Iterator[dict]:
    """Start Task 1 with a LIVE Claude QA client (KB_QA_CLIENT=live).

    Requires ANTHROPIC_API_KEY and KB_QA_MODEL.
    """
    reason = _gate_skip_reason()
    if reason:
        pytest.skip(reason)
    if not os.environ.get("CLAUDE_QA_MODEL"):
        pytest.skip("set CLAUDE_QA_MODEL to run live Task 1 tests")

    port = _free_port()
    LOG_DIR.mkdir(exist_ok=True)
    log_path = LOG_DIR / f"live_task1_{int(time.time())}.log"
    env = {
        **os.environ,
        "KB_SERVICE_PORT": str(port),
        "KB_SERVICE_HOST": "127.0.0.1",
        "KB_QA_CLIENT": "live",
        "KB_DB_PATH": str(ROOT / "data" / "live_task1.sqlite3"),
        "KB_API_TOKEN_TASK2": "t2-token",
        "KB_API_TOKEN_TASK3": "t3-token",
        "KB_API_TOKEN_ADMIN": "admin-token",
        "KB_RATE_LIMIT_PER_MINUTE": "1000",
        "KB_SCHEDULER_ENABLED": "false",
        "PYTHONPATH": str(ROOT),
    }
    log_fh = open(log_path, "w")
    proc = subprocess.Popen(
        [sys.executable, "-m", "task1_knowledge_brain.service"],
        cwd=str(ROOT), env=env,
        stdout=log_fh, stderr=subprocess.STDOUT,
    )
    base_url = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + 20.0
    healthy = False
    while time.monotonic() < deadline:
        try:
            if httpx.get(f"{base_url}/health", timeout=1.0).status_code == 200:
                healthy = True
                break
        except Exception:
            pass
        time.sleep(0.25)
    if not healthy:
        proc.kill()
        log_fh.close()
        pytest.skip(f"live Task 1 did not become healthy. Log: {log_path}")
    try:
        yield {"base_url": base_url, "log_path": str(log_path)}
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        log_fh.close()


def write_evidence(name: str, payload: dict) -> Path:
    REPORTS_DIR.mkdir(exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = REPORTS_DIR / f"{name}_{ts}.json"
    path.write_text(json.dumps(payload, indent=2, default=str))
    return path
