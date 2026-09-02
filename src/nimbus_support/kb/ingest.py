from __future__ import annotations

from nimbus_support.config import Settings, get_settings
from nimbus_support.connectors.sync import sync_connectors
from nimbus_support.kb.chunking import chunk_articles, load_help_center
from nimbus_support.kb.retrieve import TfidfRetriever, load_retriever
from nimbus_support.models import Chunk


def ingest_help_center(settings: Settings | None = None) -> list[Chunk]:
    """Sync connectors, load Nimbus docs, chunk them, write TF-IDF and/or pgvector."""
    settings = settings or get_settings()
    sync_connectors(settings)
    articles = load_help_center(settings.help_center_dir)
    chunks = chunk_articles(articles)
    backend = (settings.retrieval_backend or "tfidf").lower()
    if backend in {"tfidf", "both"}:
        retriever = TfidfRetriever.from_chunks(chunks)
        retriever.save(settings.index_dir)
    if backend in {"pgvector", "both"}:
        from nimbus_support.kb.pgvector_store import PgVectorRetriever

        PgVectorRetriever.from_settings(settings).upsert(chunks)
    return chunks


def active_retriever(settings: Settings | None = None):
    return load_retriever(settings=settings or get_settings())
