from __future__ import annotations

import re

_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE = re.compile(
    r"(?<!\w)(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]\d{4}(?!\w)"
)


def redact(text: str) -> str:
    """Mask emails and phone numbers before they leave the support desk (traces)."""
    if not text:
        return text
    masked = _EMAIL.sub("[email]", text)
    return _PHONE.sub("[phone]", masked)
