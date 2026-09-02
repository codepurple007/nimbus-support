from __future__ import annotations

import shutil
from pathlib import Path

_ALLOWED = {".md", ".csv", ".pdf", ".txt"}


class LocalFolderConnector:
    """Demo stand-in for a shared Google Drive folder or exported Sheets CSV."""

    def __init__(self, source: Path, name: str = "local") -> None:
        self.source = source
        self.name = name

    def sync(self, dest: Path) -> list[Path]:
        if not self.source.is_dir():
            return []
        dest.mkdir(parents=True, exist_ok=True)
        written: list[Path] = []
        for path in sorted(self.source.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in _ALLOWED:
                continue
            target = dest / path.name
            shutil.copy2(path, target)
            written.append(target)
        return written
