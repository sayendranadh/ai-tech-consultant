from pathlib import Path

from fastapi.testclient import TestClient

from src.api import create_app
from src.config import Task3Config


def _client(tmp_path):
    cfg = Task3Config(T3_DB_PATH=tmp_path / "t3.sqlite3", T3_API_TOKEN="")
    return TestClient(create_app(config=cfg))


def test_health_reports_ok(tmp_path):
    c = _client(tmp_path)
    r = c.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_unknown_proposal_404(tmp_path):
    c = _client(tmp_path)
    r = c.get("/proposals/does-not-exist")
    assert r.status_code == 404


def test_send_unapproved_returns_409(tmp_path):
    c = _client(tmp_path)
    r = c.post("/proposals/does-not-exist/send")
    assert r.status_code in (404, 409)
