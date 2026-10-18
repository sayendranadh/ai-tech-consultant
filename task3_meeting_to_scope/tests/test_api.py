from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api import create_app
from src.config import Task3Config
from src.ingestion.loader import load_transcript

T_DIR = Path(__file__).parent.parent / "data" / "transcripts"


@pytest.fixture
def client(tmp_path):
    cfg = Task3Config(T3_DB_PATH=tmp_path / "t3.sqlite3", T3_API_TOKEN="")
    app = create_app(config=cfg)
    with TestClient(app) as c:
        yield c


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_ingest_and_view(client):
    t = load_transcript(T_DIR / "meeting_1_website.md")
    body = {"transcript": t.model_dump(mode="json")}
    r = client.post("/transcripts", json=body)
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["transcript_id"] == "meeting_1_website"
    assert data["records_extracted"] >= 1


def test_unknown_project_returns_empty_view(client):
    r = client.get("/projects/nonexistent")
    assert r.status_code == 200
    assert r.json()["project"]["requirements"] == []
