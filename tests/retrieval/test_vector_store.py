import numpy as np
import pytest
from task1_knowledge_brain.retrieval.embedder import MockEmbedder
from task1_knowledge_brain.retrieval.vector_store import VectorStore


def test_fallback_flag_is_bool(tmp_path):
    store = VectorStore(tmp_path / "kb.sqlite3", dim=MockEmbedder().dim)
    assert isinstance(store.uses_sqlite_vec, bool)


def test_upsert_and_search(tmp_path):
    store = VectorStore(tmp_path / "kb.sqlite3", dim=8)
    import sqlite3
    con = sqlite3.connect(tmp_path / "kb.sqlite3")
    con.execute("INSERT INTO chunks (document_id, url, chunk_index, text, section_heading, content_hash, is_active, created_at) VALUES (1, 'u', 0, 'hello', 's', 'h', 1, 'now')")
    con.commit(); con.close()
    v = np.ones(8, dtype=np.float32) / np.sqrt(8)
    store.upsert_chunk_embeddings([(1, "m", v)])
    res = store.search(v, top_k=1)
    assert res and res[0].chunk_id == 1


def test_idempotent_upsert(tmp_path):
    import sqlite3
    store = VectorStore(tmp_path / "kb.sqlite3", dim=4)
    con = sqlite3.connect(tmp_path / "kb.sqlite3")
    con.execute("INSERT INTO chunks (document_id, url, chunk_index, text, section_heading, content_hash, is_active, created_at) VALUES (1, 'u', 0, 'x', 's', 'h', 1, 'now')")
    con.commit(); con.close()
    v = np.ones(4, dtype=np.float32) / 2
    store.upsert_chunk_embeddings([(1, "m", v)])
    store.upsert_chunk_embeddings([(1, "m", v)])
    con = sqlite3.connect(tmp_path / "kb.sqlite3")
    n = con.execute("SELECT COUNT(*) FROM chunk_embeddings").fetchone()[0]
    con.close()
    assert n == 1
