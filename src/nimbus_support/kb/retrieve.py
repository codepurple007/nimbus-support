from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from nimbus_support.models import Chunk, RetrievedChunk
from nimbus_support.kb.protocol import Retriever

_VECTORIZER_NAME = "tfidf_vectorizer.joblib"
_MATRIX_NAME = "tfidf_matrix.joblib"
_CHUNKS_NAME = "chunks.json"


class TfidfRetriever:
    """Local baseline retriever. Same search() contract as the future pgvector store."""

    def __init__(
        self,
        vectorizer: TfidfVectorizer,
        matrix,
        chunks: list[Chunk],
    ) -> None:
        self._vectorizer = vectorizer
        self._matrix = matrix
        self._chunks = chunks

    def search(
        self,
        query: str,
        k: int = 4,
        min_score: float = 0.05,
    ) -> list[RetrievedChunk]:
        if not query.strip() or not self._chunks:
            return []
        query_vec = self._vectorizer.transform([query])
        scores = cosine_similarity(query_vec, self._matrix)[0]
        ranked = np.argsort(scores)[::-1][:k]
        hits: list[RetrievedChunk] = []
        for index in ranked:
            score = float(scores[index])
            if score < min_score:
                continue
            hits.append(RetrievedChunk(chunk=self._chunks[index], score=score))
        return hits

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        joblib.dump(self._vectorizer, directory / _VECTORIZER_NAME)
        joblib.dump(self._matrix, directory / _MATRIX_NAME)
        payload = [asdict(chunk) for chunk in self._chunks]
        (directory / _CHUNKS_NAME).write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, directory: Path) -> TfidfRetriever:
        chunks_path = directory / _CHUNKS_NAME
        if not chunks_path.exists():
            raise FileNotFoundError(
                f"No index at {directory}. Run: python -m nimbus_support ingest"
            )
        vectorizer = joblib.load(directory / _VECTORIZER_NAME)
        matrix = joblib.load(directory / _MATRIX_NAME)
        raw = json.loads(chunks_path.read_text(encoding="utf-8"))
        chunks = [Chunk(**item) for item in raw]
        return cls(vectorizer, matrix, chunks)

    @classmethod
    def from_chunks(cls, chunks: list[Chunk]) -> TfidfRetriever:
        if not chunks:
            raise ValueError("Cannot build an index from zero chunks.")
        vectorizer = TfidfVectorizer(
            lowercase=True,
            ngram_range=(1, 2),
            min_df=1,
        )
        matrix = vectorizer.fit_transform([chunk.content for chunk in chunks])
        return cls(vectorizer, matrix, chunks)


def load_retriever(index_dir: Path | None = None, settings=None) -> Retriever:
    from nimbus_support.config import get_settings

    settings = settings or get_settings()
    backend = (settings.retrieval_backend or "tfidf").lower()
    if backend == "pgvector":
        from nimbus_support.kb.pgvector_store import PgVectorRetriever

        return PgVectorRetriever.from_settings(settings)
    return TfidfRetriever.load(index_dir or settings.index_dir)
