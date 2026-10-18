import sqlite3

from tests.service._helpers import hdr


def _create(service_env, question="How do I reset?"):
    r = service_env["client"].post(
        "/escalations",
        json={"question": question, "reason": "not in KB", "related_chunk_ids": []},
        headers=hdr("t2"),
    )
    assert r.status_code == 201
    return r.json()["id"]


def test_create_and_resolve_escalation(service_env):
    eid = _create(service_env)
    r2 = service_env["client"].post(
        f"/escalations/{eid}/resolve",
        json={"expert_answer": "Do X.", "approved_for_general_knowledge": True, "approved_for_customer_specific": False},
        headers=hdr("adm"),
    )
    assert r2.status_code == 200
    body = r2.json()
    assert body["version"] == 1
    assert body["approved_for_general_knowledge"] is True
    assert body["approved_by"] == "admin"
    # Promotion actually ran:
    assert body["promotion_run_id"], "promotion_run_id should be populated when approved_for_general"
    assert body["promotion_error"] is None


def test_resolved_approved_answer_is_retrievable(service_env):
    eid = _create(service_env, question="How do I reset?")
    r = service_env["client"].post(
        f"/escalations/{eid}/resolve",
        json={"expert_answer": "Open settings, then reset.", "approved_for_general_knowledge": True, "approved_for_customer_specific": False},
        headers=hdr("adm"),
    )
    assert r.status_code == 200

    # Synthetic document exists and has chunks
    db_path = service_env["ing_cfg"].db_path
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    doc = con.execute("SELECT * FROM documents WHERE url=?", (f"escalation://{eid}/v1",)).fetchone()
    assert doc is not None
    chunks = con.execute("SELECT * FROM chunks WHERE document_id=? AND is_active=1", (doc["id"],)).fetchall()
    assert len(chunks) >= 1
    con.close()

    # Retriever can find it via keyword search on the answer text
    res = service_env["app"].state.retriever.search("settings reset", top_k=5, mode="keyword")
    assert any("settings" in c.text.lower() for c in res.chunks)


def test_unapproved_answer_is_not_promoted(service_env):
    eid = _create(service_env)
    r = service_env["client"].post(
        f"/escalations/{eid}/resolve",
        json={"expert_answer": "Customer-specific thing.", "approved_for_general_knowledge": False, "approved_for_customer_specific": True},
        headers=hdr("adm"),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["promotion_run_id"] is None

    db_path = service_env["ing_cfg"].db_path
    con = sqlite3.connect(db_path)
    doc = con.execute("SELECT * FROM documents WHERE url=?", (f"escalation://{eid}/v1",)).fetchone()
    con.close()
    assert doc is None, "unapproved resolution must not be promoted"


def test_resolve_requires_admin(service_env):
    eid = _create(service_env)
    r2 = service_env["client"].post(
        f"/escalations/{eid}/resolve",
        json={"expert_answer": "Y", "approved_for_general_knowledge": False, "approved_for_customer_specific": False},
        headers=hdr("t2"),
    )
    assert r2.status_code == 403
    assert r2.json()["error"]["code"] == 403


def test_resolve_missing_escalation_404(service_env):
    r = service_env["client"].post(
        "/escalations/does-not-exist/resolve",
        json={"expert_answer": "Y", "approved_for_general_knowledge": False, "approved_for_customer_specific": False},
        headers=hdr("adm"),
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == 404


def test_multiple_resolutions_increment_version(service_env):
    eid = _create(service_env)
    for expected in (1, 2):
        r2 = service_env["client"].post(
            f"/escalations/{eid}/resolve",
            json={"expert_answer": f"Answer v{expected}", "approved_for_general_knowledge": False, "approved_for_customer_specific": False},
            headers=hdr("adm"),
        )
        assert r2.status_code == 200
        assert r2.json()["version"] == expected

