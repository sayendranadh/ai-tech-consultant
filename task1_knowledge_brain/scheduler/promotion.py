"""Promote an approved escalation answer into the retrieval store via the ingestion pipeline.

Contract:
- Only `approved_for_general_knowledge=True` resolutions are promoted.
- Creates a synthetic document at `escalation://<id>/v<version>`.
- Idempotent: SHA-256 of (question + answer) as content_hash; re-promotion with same
  hash → skip; different hash → new document version, old chunks deactivated.
- Indexes chunks with the configured embedder (default mock in tests).
- Sets `promotion_run_id` on the expert_answers row when done.
"""
from __future__ import annotations

import logging
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ..ingestion.chunker import chunk_article
from ..ingestion.config import IngestionConfig
from ..ingestion.manifest import ManifestStore
from ..ingestion.parser import Heading, ParsedArticle
from ..retrieval.embedder import EmbeddingProvider
from ..retrieval.vector_store import VectorStore
from ..service.escalations import synthetic_document_hash, synthetic_document_url

log = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class PromotionResult:
    promotion_run_id: str
    escalation_id: str
    version: int
    outcome: str  # "created" | "unchanged" | "skipped_not_approved"


def promote_escalation(
    cfg: IngestionConfig,
    embedder: EmbeddingProvider,
    escalation_id: str,
    version: int,
) -> PromotionResult:
    run_id = str(uuid.uuid4())
    con = sqlite3.connect(cfg.db_path)
    con.row_factory = sqlite3.Row
    try:
        esc = con.execute("SELECT * FROM escalations WHERE id=?", (escalation_id,)).fetchone()
        if esc is None:
            raise KeyError(f"escalation {escalation_id} not found")
        ans = con.execute(
            "SELECT * FROM expert_answers WHERE escalation_id=? AND version=?",
            (escalation_id, version),
        ).fetchone()
        if ans is None:
            raise KeyError(f"version {version} not found for escalation {escalation_id}")
        if not ans["approved_for_general_knowledge"]:
            return PromotionResult(run_id, escalation_id, version, "skipped_not_approved")
        question = esc["question"]
        answer = ans["text"]
    finally:
        con.close()

    doc_url = synthetic_document_url(escalation_id, version)
    doc_hash = synthetic_document_hash(question, answer)

    store = ManifestStore(cfg.db_path)
    existing = store.get(doc_url)
    if existing and existing["content_hash"] == doc_hash and existing["extraction_version"] == cfg.extraction_version:
        _mark_promotion_run(cfg, escalation_id, version, run_id)
        return PromotionResult(run_id, escalation_id, version, "unchanged")

    # Build a ParsedArticle from the escalation question+answer.
    body = f"{question}\n\n{answer}"
    article = ParsedArticle(
        title=f"Expert review: {question[:80]}",
        body_text=body,
        headings=[Heading(level=1, text="Expert answer")],
        content_hash=doc_hash,
        canonical_url=doc_url,
    )
    store.upsert_pending(doc_url, None)
    store.mark_status(doc_url, "in_progress")
    doc_id = store.write_document(doc_url, article.title, article.body_text, doc_url, doc_hash)
    chunks = chunk_article(article)
    store.write_chunks(doc_id, doc_url, [(c.index, c.text, c.section_heading, c.content_hash) for c in chunks])
    store.deactivate_stale_chunks(doc_url, keep_document_id=doc_id)
    store.mark_processed(doc_url, doc_hash, cfg.extraction_version)

    # Index the new chunks with the configured embedder.
    vs = VectorStore(cfg.db_path, embedder.dim)
    con = sqlite3.connect(cfg.db_path)
    con.row_factory = sqlite3.Row
    rows = con.execute("SELECT id, text FROM chunks WHERE document_id=? AND is_active=1", (doc_id,)).fetchall()
    con.close()
    if rows:
        vecs = embedder.embed([r["text"] for r in rows])
        vs.upsert_chunk_embeddings([(int(rows[i]["id"]), embedder.model_id, vecs[i]) for i in range(len(rows))])

    _mark_promotion_run(cfg, escalation_id, version, run_id)
    return PromotionResult(run_id, escalation_id, version, "created")


def _mark_promotion_run(cfg: IngestionConfig, escalation_id: str, version: int, run_id: str) -> None:
    con = sqlite3.connect(cfg.db_path)
    try:
        con.execute(
            "UPDATE expert_answers SET promotion_run_id=? WHERE escalation_id=? AND version=?",
            (run_id, escalation_id, version),
        )
        con.commit()
    finally:
        con.close()
