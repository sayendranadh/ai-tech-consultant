from tests.service._helpers import hdr


def test_ingestion_status_idle(service_env):
    r = service_env["client"].get("/ingestion/status", headers=hdr("t2"))
    assert r.status_code == 200
    assert r.json()["status"] == "idle"


def test_ingestion_run_requires_admin(service_env):
    r = service_env["client"].post("/ingestion/run", json={"mode": "pilot"}, headers=hdr("t2"))
    assert r.status_code == 403


def test_ingestion_run_creates_queued_job(service_env):
    r = service_env["client"].post("/ingestion/run", json={"mode": "pilot", "pilot_limit": 3}, headers=hdr("adm"))
    assert r.status_code == 202
    body = r.json()
    assert body["status"] == "queued"
    assert body["run_id"]


def test_ingestion_run_duplicate_returns_already_running(service_env):
    r1 = service_env["client"].post("/ingestion/run", json={"mode": "pilot"}, headers=hdr("adm"))
    assert r1.status_code == 202
    r2 = service_env["client"].post("/ingestion/run", json={"mode": "pilot"}, headers=hdr("adm"))
    assert r2.status_code == 200
    body = r2.json()
    assert body["status"] == "already_running"
    assert body["run_id"] == r1.json()["run_id"]
