-- Locked to OpenAI text-embedding-3-small (1536 dims).
-- Changing the embedding model means a migration + full re-ingest.

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS articles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    source_path TEXT NOT NULL,
    source_type TEXT NOT NULL,
    body TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    article_id UUID NOT NULL REFERENCES articles (id) ON DELETE CASCADE,
    chunk_index INT NOT NULL,
    content TEXT NOT NULL,
    embedding vector(1536),
    UNIQUE (article_id, chunk_index)
);

-- HNSW is usable from an empty table. IVFFlat is not.
CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw
    ON chunks
    USING hnsw (embedding vector_cosine_ops);
