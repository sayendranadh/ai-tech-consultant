"""Tests for the Knowledge Brain HTML query UI (UIB milestone)."""
from fastapi.testclient import TestClient

from task1_knowledge_brain.service.api import create_app
from task1_knowledge_brain.service.config import ServiceConfig
from task1_knowledge_brain.ingestion.config import IngestionConfig


def _client(tmp_path):
    cfg = ServiceConfig(KB_API_TOKEN_TASK2="t2", KB_API_TOKEN_TASK3="t3", KB_API_TOKEN_ADMIN="adm")
    ing = IngestionConfig(KB_DB_PATH=tmp_path / "kb.sqlite3")
    return TestClient(create_app(config=cfg, ingestion_cfg=ing))


def test_ui_home_returns_html(tmp_path):
    with _client(tmp_path) as c:
        r = c.get("/")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]
        assert "Knowledge Brain" in r.text
        assert 'id="question"' in r.text
        assert 'id="token"' in r.text
        assert 'id="submit"' in r.text


def test_ui_kb_returns_same_html(tmp_path):
    with _client(tmp_path) as c:
        r1 = c.get("/")
        r2 = c.get("/kb")
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.text == r2.text


def test_ui_form_contains_fetch_to_query(tmp_path):
    with _client(tmp_path) as c:
        r = c.get("/")
        assert 'fetch("/query"' in r.text
