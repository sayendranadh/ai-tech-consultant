"""Integration test fixtures: start a real Task 1 subprocess with fixture QA mode."""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterator

import httpx
import pytest


ROOT = Path(__file__).parent.parent
LOG_PATH = ROOT / "data" / "integration_task1.log"


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture(scope="module")
def task1_process() -> Iterator[dict]:
    port = _free_port()
    env = {
        **os.environ,
        "KB_SERVICE_PORT": str(port),
        "KB_SERVICE_HOST": "127.0.0.1",
        "KB_QA_CLIENT": "fixture",
        "KB_DB_PATH": str(ROOT / "data" / "integration_task1.sqlite3"),
        "KB_API_TOKEN_TASK2": "t2-token",
        "KB_API_TOKEN_TASK3": "t3-token",
        "KB_API_TOKEN_ADMIN": "admin-token",
        "KB_RATE_LIMIT_PER_MINUTE": "1000",
        "KB_SCHEDULER_ENABLED": "false",
        "PYTHONPATH": str(ROOT),
    }
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    log_fh = open(LOG_PATH, "w")
    proc = subprocess.Popen(
        [sys.executable, "-m", "task1_knowledge_brain.service"],
        cwd=str(ROOT),
        env=env,
        stdout=log_fh,
        stderr=subprocess.STDOUT,
    )
    base_url = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + 20.0
    healthy = False
    while time.monotonic() < deadline:
        try:
            r = httpx.get(f"{base_url}/health", timeout=1.0)
            if r.status_code == 200:
                healthy = True
                break
        except Exception:
            pass
        time.sleep(0.25)
    if not healthy:
        proc.kill()
        log_fh.close()
        raise RuntimeError(f"Task 1 did not become healthy. See {LOG_PATH}")
    try:
        yield {
            "base_url": base_url,
            "task2_token": "t2-token",
            "task3_token": "t3-token",
            "admin_token": "admin-token",
            "proc": proc,
            "log_path": LOG_PATH,
        }
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        log_fh.close()
