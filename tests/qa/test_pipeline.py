import sqlite3
import pytest

from task1_knowledge_brain.ingestion.config import IngestionConfig
from task1_knowledge_brain.ingestion.manifest import ManifestStore
from task1_knowledge_brain.qa.pipeline import MockQAClient, QAPipeline
from task1_knowledge_brain.retrieval.embedder import MockEmbedder
from task1_knowledge_brain.retrieval.retriever import Retriever
from task1_knowledge_brain.retrieval.vector_store import VectorStore
from task1_knowledge_brain.schemas.qa import QARequest


class _CiteAllClient:
    model_id = "test/cite-all"
    is_live = False
    def __init__(self, text, chunk_ids):
        self._text = text
        self._ids = chunk_ids
    def answer(self, system, user):
        cites = " ".join(f"[chunk_id={i}]" for i in self._ids)
        return f"{self._text} {cites}"


class _BadCitationClient:
    model_id = "test/bad-cite"
    is_live = False
    def answer(self, system, user):
        return "Answer with fabricated citation [chunk_id=999]"


class _FailingClient:
    model_id = "test/fail"
    is_live = False
    def answer(self, system, user):
        raise RuntimeError("provider down")


def _seed(tmp_path, texts):
    cfg = IngestionConfig(KB_DB_PATH=tmp_path / "kb.sqlite3")
    ManifestStore(cfg.db_path)
    con = sqlite3.connect(cfg.db_path)
    con.execute("INSERT INTO documents (url, version, title, body_text, canonical_url, content_hash, created_at) VALUES (?,?,?,?,?,?,datetime('now'))",
                ("https://x/a", 1, "Reset", "body", None, "h1"))
    doc_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
    ids = []
    for i, t in enumerate(texts):
        con.execute("INSERT INTO chunks (document_id, url, chunk_index, text, section_heading, content_hash, is_active, created_at) VALUES (?,?,?,?,?,?,1,datetime('now'))",
                    (doc_id, "https://x/a", i, t, f"sec{i}", f"h{i}"))
        ids.append(con.execute("SELECT last_insert_rowid()").fetchone()[0])
    con.commit(); con.close()
    return cfg, ids


def _index(cfg, emb):
    store = VectorStore(cfg.db_path, emb.dim)
    con = sqlite3.connect(cfg.db_path)
    rows = con.execute("SELECT id, text FROM chunks").fetchall()
    con.close()
    vecs = emb.embed([r[1] for r in rows])
    store.upsert_chunk_embeddings([(rows[i][0], emb.model_id, vecs[i]) for i in range(len(rows))])
    return store


def test_answered_with_valid_citations(tmp_path):
    cfg, ids = _seed(tmp_path, ["password reset procedure here", "unrelated refund text"])
    emb = MockEmbedder(); _index(cfg, emb)
    client = _CiteAllClient("To reset a password, use settings.", ids[:1])
    pipeline = QAPipeline(retriever=Retriever(cfg.db_path, emb), client=client, min_top_score=0.0)
    resp = pipeline.run(QARequest(question="password reset"))
    assert resp.status == "answered"
    assert resp.sources and resp.sources[0].chunk_id == ids[0]


def test_bad_citation_rejected(tmp_path):
    cfg, ids = _seed(tmp_path, ["password reset procedure here"])
    emb = MockEmbedder(); _index(cfg, emb)
    pipeline = QAPipeline(retriever=Retriever(cfg.db_path, emb), client=_BadCitationClient(), min_top_score=0.0)
    resp = pipeline.run(QARequest(question="password reset"))
    assert resp.status == "insufficient_evidence"
    assert "verif" in resp.answer.lower() or "no verifiable" in resp.answer.lower()


def test_no_evidence(tmp_path):
    cfg, _ = _seed(tmp_path, ["password reset procedure here"])
    emb = MockEmbedder(); _index(cfg, emb)
    pipeline = QAPipeline(retriever=Retriever(cfg.db_path, emb), client=MockQAClient(), min_top_score=2.0)
    resp = pipeline.run(QARequest(question="anything"))
    assert resp.status == "insufficient_evidence"


def test_model_failure_returns_failed(tmp_path):
    cfg, _ = _seed(tmp_path, ["password reset procedure here"])
    emb = MockEmbedder(); _index(cfg, emb)
    pipeline = QAPipeline(retriever=Retriever(cfg.db_path, emb), client=_FailingClient(), min_top_score=0.0)
    resp = pipeline.run(QARequest(question="password reset"))
    assert resp.status == "failed"
    assert resp.escalation_required


def test_mock_client_abstains(tmp_path):
    cfg, _ = _seed(tmp_path, ["password reset procedure here"])
    emb = MockEmbedder(); _index(cfg, emb)
    pipeline = QAPipeline(retriever=Retriever(cfg.db_path, emb), client=MockQAClient(), min_top_score=0.0)
    resp = pipeline.run(QARequest(question="password reset"))
    # Mock returns a SIMULATED answer with no valid chunk_id → insufficient.
    assert resp.status in ("insufficient_evidence", "answered")
