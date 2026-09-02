from __future__ import annotations

import csv
import re
from pathlib import Path

from nimbus_support.models import Article, Chunk

_HEADING = re.compile(r"^#\s+(.+)$", re.MULTILINE)
_SLUG = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    slug = _SLUG.sub("-", value.lower()).strip("-")
    return slug or "article"


def load_help_center(directory: Path) -> list[Article]:
    if not directory.is_dir():
        raise FileNotFoundError(f"Help center not found: {directory}")

    articles: list[Article] = []
    for path in sorted(directory.rglob("*")):
        if not path.is_file() or path.name.startswith("."):
            continue
        suffix = path.suffix.lower()
        if suffix == ".md":
            articles.append(_load_markdown(path))
        elif suffix == ".pdf":
            from nimbus_support.kb.pdf import load_pdf

            articles.append(load_pdf(path))
        elif suffix in {".csv", ".xlsx"}:
            if suffix == ".xlsx":
                raise ValueError(
                    f"{path.name}: convert Excel to CSV, or export .csv from Excel."
                )
            articles.append(_load_csv(path))
    if not articles:
        raise FileNotFoundError(f"No .md, .csv, or .pdf files in {directory}")
    return articles


def chunk_articles(
    articles: list[Article],
    *,
    chunk_size: int = 700,
    overlap: int = 120,
) -> list[Chunk]:
    chunks: list[Chunk] = []
    for article in articles:
        parts = (
            _chunk_csv_body(article.body)
            if article.source_type == "csv"
            else _chunk_text(article.body, chunk_size=chunk_size, overlap=overlap)
        )
        for index, content in enumerate(parts):
            chunks.append(
                Chunk(
                    article_slug=article.slug,
                    article_title=article.title,
                    source_path=article.source_path,
                    source_type=article.source_type,
                    chunk_index=index,
                    content=content,
                )
            )
    return chunks


def _load_markdown(path: Path) -> Article:
    body = path.read_text(encoding="utf-8").strip()
    match = _HEADING.search(body)
    title = match.group(1).strip() if match else path.stem.replace("-", " ").title()
    return Article(
        slug=path.stem,
        title=title,
        source_path=str(path),
        source_type="markdown",
        body=body,
    )


def _load_csv(path: Path) -> Article:
    """Turn a catalog spreadsheet into readable sentences, one per row."""
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    lines = []
    for row in rows:
        parts = [f"{key}={value}" for key, value in row.items() if value]
        lines.append("Catalog row: " + "; ".join(parts))
    title = path.stem.replace("-", " ").title()
    return Article(
        slug=path.stem,
        title=title,
        source_path=str(path),
        source_type="csv",
        body="\n".join(lines),
    )


def _chunk_csv_body(body: str) -> list[str]:
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    return lines or [body]


def _chunk_text(text: str, *, chunk_size: int, overlap: int) -> list[str]:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if len(cleaned) <= chunk_size:
        return [cleaned]

    chunks: list[str] = []
    start = 0
    while start < len(cleaned):
        end = min(start + chunk_size, len(cleaned))
        chunks.append(cleaned[start:end].strip())
        if end == len(cleaned):
            break
        start = max(end - overlap, start + 1)
    return chunks
