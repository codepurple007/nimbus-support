from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class WindowBufferStore:
    """Last-K chat turns, keyed by session id.

    Matches n8n Simple Memory (`memoryBufferWindow` in n8n-io/n8n):
    https://github.com/n8n-io/n8n/blob/master/packages/@n8n/nodes-langchain/nodes/memory/MemoryBufferWindow/MemoryBufferWindow.node.ts

    n8n default ``contextWindowLength`` is 5 interactions (human+ai pairs).
    We persist JSON so CLI and the hosted chat share a session without Postgres.
    """

    def __init__(self, path: Path, k: int = 5) -> None:
        self.path = path
        self.k = k

    def load(self, session_id: str) -> list[dict[str, str]]:
        session = self._payload()["sessions"].get(session_id) or {"messages": []}
        messages = session.get("messages") or []
        return messages[-(self.k * 2) :]

    def append(self, session_id: str, human: str, ai: str) -> list[dict[str, str]]:
        payload = self._payload()
        session = payload["sessions"].setdefault(session_id, {"messages": []})
        session["messages"].extend(
            [
                {"role": "human", "content": human},
                {"role": "ai", "content": ai},
            ]
        )
        session["messages"] = session["messages"][-(self.k * 2) :]
        session["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        payload["sessions"][session_id] = session
        self._save(payload)
        return list(session["messages"])

    def search_query(self, session_id: str, query: str) -> str:
        """Current question plus the last human turn, so follow-ups retrieve."""
        messages = self.load(session_id)
        prior = ""
        for message in reversed(messages):
            if message.get("role") == "human":
                prior = (message.get("content") or "").strip()
                break
        if prior and prior.lower() != query.strip().lower():
            return f"{prior} {query.strip()}".strip()
        return query.strip()

    def _payload(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"sessions": {}}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _save(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
