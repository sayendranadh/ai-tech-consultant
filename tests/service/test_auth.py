from tests.service._helpers import hdr


def test_query_without_token_401(service_env):
    r = service_env["client"].post("/query", json={"question": "hi"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == 401
    assert "bearer" in r.json()["error"]["message"].lower()


def test_query_with_bad_token_401(service_env):
    r = service_env["client"].post("/query", json={"question": "hi"}, headers=hdr("nope"))
    assert r.status_code == 401
    assert r.json()["error"]["code"] == 401


def test_task2_can_query(service_env):
    r = service_env["client"].post("/query", json={"question": "hi"}, headers=hdr("t2"))
    assert r.status_code == 200


def test_task2_cannot_run_ingestion(service_env):
    r = service_env["client"].post("/ingestion/run", json={"mode": "pilot"}, headers=hdr("t2"))
    assert r.status_code == 403
    assert r.json()["error"]["code"] == 403
