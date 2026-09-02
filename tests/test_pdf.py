from io import BytesIO

from nimbus_support.config import PROJECT_ROOT
from nimbus_support.kb.chunking import load_help_center
from nimbus_support.kb.pdf import load_pdf
from nimbus_support.tracing import observation, tracing_enabled


def test_pdf_loader_extracts_text(tmp_path) -> None:
    path = tmp_path / "nimbus-faq.pdf"
    path.write_bytes(_pdf_with_text("Nimbus password reset uses Forgot password."))
    article = load_pdf(path)
    assert article.source_type == "pdf"
    assert "Forgot password" in article.body
    assert article.slug == "nimbus-faq"


def test_help_center_still_loads_markdown() -> None:
    articles = load_help_center(PROJECT_ROOT / "data" / "help-center")
    assert {a.slug for a in articles} >= {"password-reset", "refund-policy"}


def test_tracing_is_off_without_keys() -> None:
    assert tracing_enabled() is False
    with observation("retrieve") as span:
        assert span is None


def _pdf_with_text(text: str) -> bytes:
    # Minimal PDF 1.4 with a single Helvetica string.
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 12 Tf 50 700 Td ({escaped}) Tj ET".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = [0]
    for i, obj in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(f"{i} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = out.tell()
    out.write(f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n".encode())
    for off in offsets[1:]:
        out.write(f"{off:010d} 00000 n \n".encode())
    out.write(
        f"trailer << /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return out.getvalue()
