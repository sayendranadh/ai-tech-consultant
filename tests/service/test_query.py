from tests.service._helpers import hdr


def test_query_malformed_422(service_env):
    r = service_env["client"].post("/query", json={"nope": "x"}, headers=hdr("t2"))
    assert r.status_code == 422
    body = r.json()
    assert body["error"]["code"] == 422
    assert body["error"]["message"] == "validation error"
    # FastAPI validation details present
    assert any("loc" in d for d in body["error"]["details"])


def test_query_returns_insufficient_evidence_when_no_data(service_env):
    r = service_env["client"].post("/query", json={"question": "anything"}, headers=hdr("t2"))
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in ("insufficient_evidence", "failed")
    assert body["escalation_required"] is True
