from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Article:
    slug: str
    title: str
    source_path: str
    source_type: str
    body: str


@dataclass(frozen=True)
class Chunk:
    article_slug: str
    article_title: str
    source_path: str
    source_type: str
    chunk_index: int
    content: str


@dataclass(frozen=True)
class RetrievedChunk:
    chunk: Chunk
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_citation(self) -> dict[str, Any]:
        return {
            "slug": self.chunk.article_slug,
            "title": self.chunk.article_title,
            "source_path": self.chunk.source_path,
            "score": round(self.score, 4),
            "excerpt": self.chunk.content[:240],
        }
