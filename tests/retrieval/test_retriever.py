import sqlite3

from task1_knowledge_brain.ingestion.config import IngestionConfig
from task1_knowledge_brain.ingestion.manifest import ManifestStore
from task1_knowledge_brain.retrieval.embedder import MockEmbedder
from task1_knowledge_brain.retrieval.retriever import Retriever
from task1_knowledge_brain.retrieval.vector_store import VectorStore


def _seed(tmp_path):
    cfg = IngestionConfig(KB_DB_PATH=tmp_path / "kb.sqlite3")
    ManifestStore(cfg.db_path)
    con = sqlite3.connect(cfg.db_path)
    con.execute(
        "INSERT INTO documents (url, version, title, body_text, canonical_url, content_hash, created_at) "
        "VALUES (?,?,?,?,?,?,datetime('now'))",
        ("https://x/a", 1, "Reset", "body", None, "h1"),
    )
    doc_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
    for i, t in enumerate(["password reset procedure", "settings screen description", "refund policy unknown"]):
        con.execute(
            "INSERT INTO chunks (document_id, url, chunk_index, text, section_heading, content_hash, is_active, created_at) "
            "VALUES (?,?,?,?,?,?,1,datetime('now'))",
            (doc_id, "https://x/a", i, t, f"sec{i}", f"h{i}"),
        )
    con.commit()
    con.close()
    return cfg


def test_semantic_search_returns_active_chunks(tmp_path):
    cfg = _seed(tmp_path)
    emb = MockEmbedder()
    store = VectorStore(cfg.db_path, emb.dim)  # bootstrap occurs here; FTS backfilled
    con = sqlite3.connect(cfg.db_path)
    rows = con.execute("SELECT id, text FROM chunks").fetchall()
    con.close()
    vecs = emb.embed([r[1] for r in rows])
    store.upsert_chunk_embeddings([(rows[i][0], emb.model_id, vecs[i]) for i in range(len(rows))])
    retriever = Retriever(cfg.db_path, emb)
    res = retriever.search("password reset", top_k=3, mode="semantic")
    assert res.chunks, "semantic search should return chunks"
    # ADR-018: cosine similarity range is [-1, 1].
    assert all(-1.01 <= c.score <= 1.01 for c in res.chunks)


def test_keyword_search(tmp_path):
    cfg = _seed(tmp_path)
    emb = MockEmbedder()
    VectorStore(cfg.db_path, emb.dim)  # FTS backfill from existing chunks
    retriever = Retriever(cfg.db_path, emb)
    res = retriever.search("password", top_k=3, mode="keyword")
    assert res.chunks
    assert any("password" in c.text for c in res.chunks)


def test_inactive_chunks_excluded(tmp_path):
    cfg = _seed(tmp_path)
    emb = MockEmbedder()
    store = VectorStore(cfg.db_path, emb.dim)
    con = sqlite3.connect(cfg.db_path)
    rows = con.execute("SELECT id, text FROM chunks").fetchall()
    con.close()
    vecs = emb.embed([r[1] for r in rows])
    store.upsert_chunk_embeddings([(rows[i][0], emb.model_id, vecs[i]) for i in range(len(rows))])
    con = sqlite3.connect(cfg.db_path)
    con.execute("UPDATE chunks SET is_active = 0 WHERE id = ?", (rows[0][0],))
    con.commit()
    con.close()
    retriever = Retriever(cfg.db_path, emb)
    res = retriever.search("anything", top_k=10, mode="semantic")
    assert rows[0][0] not in [c.chunk_id for c in res.chunks]
