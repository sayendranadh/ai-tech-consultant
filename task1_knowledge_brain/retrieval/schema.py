"""SQL additions for retrieval: embeddings, FTS5, image descriptions.

PREREQUISITE: the ingestion schema (chunks, documents, manifest, images) must already exist.
VectorStore._bootstrap() ensures this by calling ManifestStore first.
"""

EMBEDDING_SCHEMA = """
CREATE TABLE IF NOT EXISTS chunk_embeddings (
    chunk_id INTEGER PRIMARY KEY,
    model_id TEXT NOT NULL,
    dim INTEGER NOT NULL,
    vec BLOB NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(chunk_id) REFERENCES chunks(id)
);
CREATE INDEX IF NOT EXISTS idx_chunk_embeddings_model ON chunk_embeddings(model_id);

CREATE TABLE IF NOT EXISTS image_descriptions (
    image_id INTEGER PRIMARY KEY,
    model_id TEXT NOT NULL,
    description TEXT NOT NULL,
    status TEXT NOT NULL,
    uncertainty TEXT,
    extraction_version INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(image_id) REFERENCES images(id)
);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    text,
    section_heading,
    url UNINDEXED,
    content='chunks',
    content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
    INSERT INTO chunks_fts(rowid, text, section_heading, url)
    VALUES (new.id, new.text, new.section_heading, new.url);
END;
CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, text, section_heading, url)
    VALUES ('delete', old.id, old.text, old.section_heading, old.url);
END;
CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, text, section_heading, url)
    VALUES ('delete', old.id, old.text, old.section_heading, old.url);
    INSERT INTO chunks_fts(rowid, text, section_heading, url)
    VALUES (new.id, new.text, new.section_heading, new.url);
END;
"""
