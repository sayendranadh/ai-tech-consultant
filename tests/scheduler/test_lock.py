import pytest

from task1_knowledge_brain.ingestion.config import IngestionConfig
from task1_knowledge_brain.scheduler.daily_job import _acquire_source_lock


def test_lock_prevents_concurrent_run(tmp_path):
    cfg = IngestionConfig(KB_DB_PATH=tmp_path / "kb.sqlite3")
    # First lock succeeds
    con = _acquire_source_lock(cfg, "support.brilliantdirectories.com")
    try:
        with pytest.raises(RuntimeError):
            _acquire_source_lock(cfg, "support.brilliantdirectories.com")
    finally:
        con.execute("COMMIT")
        con.close()
