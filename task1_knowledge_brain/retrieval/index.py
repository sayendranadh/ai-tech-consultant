"""Build real embeddings for active chunks. Run manually; NOT invoked by tests."""
from __future__ import annotations

import argparse
import logging

from .embedder import SentenceTransformerEmbedder
from .vector_store import VectorStore
from ..ingestion.config import IngestionConfig

log = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build real embeddings for active chunks")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=args.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    cfg = IngestionConfig()
    embedder = SentenceTransformerEmbedder()
    store = VectorStore(cfg.db_path, dim=embedder.dim)

    import sqlite3
    con = sqlite3.connect(cfg.db_path)
    con.row_factory = sqlite3.Row
    rows = con.execute("SELECT id, text FROM chunks WHERE is_active = 1").fetchall()
    con.close()

    if not rows:
        log.info("no active chunks; nothing to index")
        return

    texts = [r["text"] for r in rows]
    ids = [int(r["id"]) for r in rows]
    vecs = embedder.embed(texts)
    written = store.upsert_chunk_embeddings([(ids[i], embedder.model_id, vecs[i]) for i in range(len(ids))])
    print(f"indexed {written} chunks with model {embedder.model_id}")


if __name__ == "__main__":
    main()
