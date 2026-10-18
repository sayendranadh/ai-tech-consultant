from task1_knowledge_brain.ingestion.config import IngestionConfig
from task1_knowledge_brain.scheduler.setup import build_scheduler


def test_scheduler_uses_max_instances_one(tmp_path):
    cfg = IngestionConfig(KB_DB_PATH=tmp_path / "kb.sqlite3")
    scheduler = build_scheduler(cfg)
    job = scheduler.get_job("daily_ingestion")
    assert job.max_instances == 1
    assert job.coalesce is True
