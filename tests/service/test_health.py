def test_health_reports_degraded_when_models_mocked(service_env):
    r = service_env["client"].get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "degraded"
    assert body["checks"]["db"] == "ok"
    assert body["checks"]["vision_model"] == "mocked"
    assert body["checks"]["qa_model"] == "mocked"
