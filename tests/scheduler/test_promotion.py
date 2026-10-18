from task1_knowledge_brain.ingestion.config import IngestionConfig
from task1_knowledge_brain.ingestion.manifest import ManifestStore
from task1_knowledge_brain.retrieval.embedder import MockEmbedder
from task1_knowledge_brain.retrieval.retriever import Retriever
from task1_knowledge_brain.scheduler.promotion import promote_escalation
from task1_knowledge_brain.service.escalations import EscalationStore


def _seed_escalation(cfg, approved_general: bool):
    esc = EscalationStore(cfg.db_path)
    row = esc.create(question="How do I reset?", reason="not in KB", related_chunk_ids=[], created_by="task2")
    # embedder=None → resolve() records the resolution but does not promote (we invoke promotion explicitly below).
    esc.resolve(
        row["id"],
        expert_answer="Open settings, then reset.",
        approved_for_general=approved_general,
        approved_for_customer=False,
        approver="admin",
        embedder=None,
    )
    return row["id"]


def test_promotion_indexes_approved_answer(tmp_path):
    cfg = IngestionConfig(KB_DB_PATH=tmp_path / "kb.sqlite3")
    ManifestStore(cfg.db_path)
    eid = _seed_escalation(cfg, approved_general=True)
    result = promote_escalation(cfg, MockEmbedder(), eid, version=1)
    assert result.outcome in ("created", "unchanged")

    retriever = Retriever(cfg.db_path, MockEmbedder())
    res = retriever.search("reset settings", top_k=5, mode="keyword")
    assert any("settings" in c.text.lower() for c in res.chunks)


def test_promotion_skips_unapproved(tmp_path):
    cfg = IngestionConfig(KB_DB_PATH=tmp_path / "kb.sqlite3")
    ManifestStore(cfg.db_path)
    eid = _seed_escalation(cfg, approved_general=False)
    result = promote_escalation(cfg, MockEmbedder(), eid, version=1)
    assert result.outcome == "skipped_not_approved"


def test_promotion_is_idempotent(tmp_path):
    cfg = IngestionConfig(KB_DB_PATH=tmp_path / "kb.sqlite3")
    ManifestStore(cfg.db_path)
    eid = _seed_escalation(cfg, approved_general=True)
    r1 = promote_escalation(cfg, MockEmbedder(), eid, version=1)
    r2 = promote_escalation(cfg, MockEmbedder(), eid, version=1)
    assert r1.outcome == "created"
    assert r2.outcome == "unchanged"

    store = ManifestStore(cfg.db_path)
    assert store.count("documents") == 1

