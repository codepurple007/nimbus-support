from __future__ import annotations

from typing import Protocol

from nimbus_support.models import RetrievedChunk


class Retriever(Protocol):
    """Same contract as n8n Vector Store retrieve: query in, scored chunks out."""

    def search(
        self,
        query: str,
        k: int = 4,
        min_score: float = 0.05,
    ) -> list[RetrievedChunk]:
        ...
