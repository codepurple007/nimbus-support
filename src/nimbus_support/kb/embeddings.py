"""Embeddings for pgvector.

n8n analog: Embeddings Google Gemini (`embeddingsGoogleGemini`).
gemini-embedding-001 defaults to 3072 dims in n8n; we request 1536 to match sql/schema.sql.
"""

from __future__ import annotations

from nimbus_support.config import Settings, get_settings

EMBEDDING_DIM = 1536


class Embedder:
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError

    def embed_query(self, text: str) -> list[float]:
        raise NotImplementedError


class GeminiEmbedder(Embedder):
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        if not self._settings.gemini_key:
            raise RuntimeError("GEMINI_API_KEY is required for pgvector ingest/search")
        from google import genai
        from google.genai import types

        self._types = types
        self._client = genai.Client(api_key=self._settings.gemini_key)
        self._model = self._settings.gemini_embedding_model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text, "RETRIEVAL_DOCUMENT") for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text, "RETRIEVAL_QUERY")

    def _embed(self, text: str, task: str) -> list[float]:
        response = self._client.models.embed_content(
            model=self._model,
            contents=text or " ",
            config=self._types.EmbedContentConfig(
                task_type=task,
                output_dimensionality=EMBEDDING_DIM,
            ),
        )
        values = response.embeddings[0].values
        return [float(v) for v in values]
