from pathlib import Path

from fastapi.testclient import TestClient

from src.api import create_app
from src.config import Task3Config


def _client(tmp_path):
    cfg = Task3Config(T3_DB_PATH=tmp_path / "t3.sqlite3", T3_API_TOKEN="")
    return TestClient(create_app(config=cfg))


def test_compare_returns_report_and_markdown(tmp_path):
    with _client(tmp_path) as c:
        r = c.post("/projects/project_website/followup/meeting_3_followup/compare")
        assert r.status_code == 200, r.text
        body = r.json()
        assert "report" in body and "markdown" in body and "revised_proposal" in body
        assert body["report"]["followup_transcript_id"] == "meeting_3_followup"
        assert body["revised_proposal"]["status"] == "revised"
        assert "# Change Report" in body["markdown"]


def test_compare_unknown_project_404(tmp_path):
    with _client(tmp_path) as c:
        r = c.post("/projects/nonexistent/followup/meeting_3_followup/compare")
        assert r.status_code == 404


def test_send_before_approve_409(tmp_path):
    with _client(tmp_path) as c:
        r = c.post("/projects/project_website/followup/meeting_3_followup/compare")
        rid = r.json()["report"]["report_id"]
        r2 = c.post(f"/change-reports/{rid}/send")
        assert r2.status_code == 409


def test_approve_then_send_simulated(tmp_path):
    with _client(tmp_path) as c:
        r = c.post("/projects/project_website/followup/meeting_3_followup/compare")
        rid = r.json()["report"]["report_id"]
        r2 = c.post(f"/change-reports/{rid}/approve", json={"approved_by": "alice"})
        assert r2.status_code == 200, r2.text
        r3 = c.post(f"/change-reports/{rid}/send")
        assert r3.status_code == 200, r3.text
        assert r3.json()["is_simulated"] is True
        assert r3.json()["delivery_status"] == "simulated_sent"


def test_unknown_report_404_or_409(tmp_path):
    with _client(tmp_path) as c:
        assert c.post("/change-reports/nope/approve", json={"approved_by": "alice"}).status_code == 404
        assert c.post("/change-reports/nope/send").status_code in (404, 409)
