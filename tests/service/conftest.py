import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
from fastapi.testclient import TestClient

from task1_knowledge_brain.service.api import create_app
from task1_knowledge_brain.service.config import ServiceConfig
from task1_knowledge_brain.ingestion.config import IngestionConfig
from task1_knowledge_brain.retrieval.embedder import MockEmbedder


@pytest.fixture
def service_env(tmp_path):
    cfg = ServiceConfig(
        KB_API_TOKEN_TASK2="t2",
        KB_API_TOKEN_TASK3="t3",
        KB_API_TOKEN_ADMIN="adm",
        KB_RATE_LIMIT_PER_MINUTE=1000,
    )
    ing = IngestionConfig(KB_DB_PATH=tmp_path / "kb.sqlite3")
    app = create_app(config=cfg, ingestion_cfg=ing, embedder=MockEmbedder())
    with TestClient(app) as client:
        yield {"client": client, "ing_cfg": ing, "app": app}
