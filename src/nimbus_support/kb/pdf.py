"""PDF loader. Same job as n8n Default Data Loader → PDF (N8nPdfLoader / pdf-parse).

n8n-io/n8n: packages/@n8n/ai-utilities/src/utils/loaders/n8n-pdf-loader.ts
Pages are extracted, then concatenated (splitPages=false analog).
"""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader

from nimbus_support.kb.chunking import slugify
from nimbus_support.models import Article


def load_pdf(path: Path) -> Article:
    reader = PdfReader(str(path))
    pages: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        cleaned = " ".join(text.split())
        if cleaned:
            pages.append(cleaned)
    body = "\n\n".join(pages).strip()
    if not body:
        raise ValueError(f"{path.name}: PDF had no extractable text")
    title = (reader.metadata.title if reader.metadata else None) or path.stem.replace(
        "-", " "
    ).title()
    return Article(
        slug=slugify(path.stem),
        title=str(title),
        source_path=str(path),
        source_type="pdf",
        body=body,
    )
