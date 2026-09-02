from __future__ import annotations

from pathlib import Path
from typing import Protocol


class Connector(Protocol):
    """Knowledge connector: sync files into the help-center directory, then ingest."""

    name: str

    def sync(self, dest: Path) -> list[Path]:
        """Copy or download files into dest. Returns written paths."""
        ...
