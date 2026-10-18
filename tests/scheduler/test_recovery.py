from task1_knowledge_brain.ingestion.config import IngestionConfig
from task1_knowledge_brain.ingestion.manifest import ManifestStore
from task1_knowledge_brain.scheduler.recovery import recover_interrupted


def test_recovery_resets_in_progress(tmp_path):
    cfg = IngestionConfig(KB_DB_PATH=tmp_path / "kb.sqlite3")
    store = ManifestStore(cfg.db_path)
    store.upsert_pending("https://x/a", None)
    store.mark_status("https://x/a", "in_progress")
    n = recover_interrupted(cfg)
    assert n == 1
    row = store.get("https://x/a")
    assert row["processing_status"] == "pending"
