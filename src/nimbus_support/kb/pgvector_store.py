"""Postgres PGVector store.

n8n analog: Postgres PGVector Store (`vectorStorePGVector`) — insert + retrieve,
cosine distance. We use this project's articles/chunks schema (not n8n_vectors).
https://github.com/n8n-io/n8n/blob/master/packages/@n8n/nodes-langchain/nodes/vector_store/VectorStorePGVector/VectorStorePGVector.node.ts
"""

from __future__ import annotations

from pathlib import Path

from nimbus_support.config import PROJECT_ROOT, Settings, get_settings
from nimbus_support.kb.embeddings import EMBEDDING_DIM, Embedder, GeminiEmbedder
from nimbus_support.models import Chunk, RetrievedChunk

_SCHEMA = PROJECT_ROOT / "sql" / "schema.sql"


class PgVectorRetriever:
    def __init__(self, conninfo: str, embedder: Embedder) -> None:
        self._conninfo = conninfo
        self._embedder = embedder

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> PgVectorRetriever:
        settings = settings or get_settings()
        return cls(settings.database_url, GeminiEmbedder(settings))

    def upsert(self, chunks: list[Chunk]) -> None:
        if not chunks:
            raise ValueError("Cannot upsert zero chunks")
        vectors = self._embedder.embed_documents([chunk.content for chunk in chunks])
        with self._connect() as conn:
            self._ensure_schema(conn)
            with conn.cursor() as cur:
                cur.execute("TRUNCATE articles CASCADE")
                by_slug: dict[str, Chunk] = {}
                for chunk in chunks:
                    by_slug.setdefault(chunk.article_slug, chunk)
                article_ids: dict[str, str] = {}
                for slug, sample in by_slug.items():
                    cur.execute(
                        """
                        INSERT INTO articles (slug, title, source_path, source_type, body)
                        VALUES (%s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (
                            slug,
                            sample.article_title,
                            sample.source_path,
                            sample.source_type,
                            sample.content,
                        ),
                    )
                    article_ids[slug] = str(cur.fetchone()[0])
                for chunk, vector in zip(chunks, vectors, strict=True):
                    if len(vector) != EMBEDDING_DIM:
                        raise ValueError(
                            f"Embedding dim {len(vector)} != schema {EMBEDDING_DIM}"
                        )
                    cur.execute(
                        """
                        INSERT INTO chunks (article_id, chunk_index, content, embedding)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (
                            article_ids[chunk.article_slug],
                            chunk.chunk_index,
                            chunk.content,
                            vector,
                        ),
                    )
            conn.commit()

    def search(
        self,
        query: str,
        k: int = 4,
        min_score: float = 0.05,
    ) -> list[RetrievedChunk]:
        if not query.strip():
            return []
        vector = self._embedder.embed_query(query)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        a.slug,
                        a.title,
                        a.source_path,
                        a.source_type,
                        c.chunk_index,
                        c.content,
                        1 - (c.embedding <=> %s::vector) AS score
                    FROM chunks c
                    JOIN articles a ON a.id = c.article_id
                    ORDER BY c.embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (vector, vector, k),
                )
                rows = cur.fetchall()
        hits: list[RetrievedChunk] = []
        for row in rows:
            score = float(row[6])
            if score < min_score:
                continue
            hits.append(
                RetrievedChunk(
                    chunk=Chunk(
                        article_slug=row[0],
                        article_title=row[1],
                        source_path=row[2],
                        source_type=row[3],
                        chunk_index=int(row[4]),
                        content=row[5],
                    ),
                    score=score,
                )
            )
        return hits

    def _connect(self):
        import psycopg
        from pgvector.psycopg import register_vector

        conn = psycopg.connect(self._conninfo)
        register_vector(conn)
        return conn

    def _ensure_schema(self, conn) -> None:
        raw = Path(_SCHEMA).read_text(encoding="utf-8")
        with conn.cursor() as cur:
            for stmt in raw.split(";"):
                body = "\n".join(
                    line
                    for line in stmt.splitlines()
                    if line.strip() and not line.strip().startswith("--")
                ).strip()
                if body:
                    cur.execute(body)
        conn.commit()
