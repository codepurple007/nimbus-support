from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

# Matches n8n HTTP Request Tool style: look up by id, never invent a row.
_ORDER_ID = re.compile(
    r"(?:order\s*(?:number|#|id)?\s*#?|#)(\d{3,6})\b",
    re.IGNORECASE,
)
_BARE_HASH = re.compile(r"#(\d{3,6})\b")


def extract_order_id(query: str) -> str | None:
    match = _ORDER_ID.search(query) or _BARE_HASH.search(query)
    return match.group(1) if match else None


class OrderStore:
    """Fake store API. Same job as an n8n HTTP Request tool against a shop."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._rows = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    def get(self, order_id: str) -> dict[str, Any] | None:
        row = self._rows.get(str(order_id))
        if row is None:
            return None
        return {"id": str(order_id), **row}
