from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol


class ChatMemory(Protocol):
    def load(self, session_id: str) -> list[dict[str, str]]: ...
    def append(self, session_id: str, human: str, ai: str) -> list[dict[str, str]]: ...
    def search_query(self, session_id: str, query: str) -> str: ...


class WindowBufferStore:
    """Last-K chat turns, keyed by session id. Persisted to JSON."""

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
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"sessions": {}}

    def _save(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


class PgChatMemory:
    """PostgreSQL chat memory implementation."""

    def __init__(self, conninfo: str, k: int = 5) -> None:
        self._conninfo = conninfo
        self.k = k

    def load(self, session_id: str) -> list[dict[str, str]]:
        import psycopg
        with psycopg.connect(self._conninfo) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT messages FROM sessions WHERE session_id = %s",
                    (session_id,),
                )
                row = cur.fetchone()
                if not row:
                    return []
                messages = row[0]
                return messages[-(self.k * 2) :]

    def append(self, session_id: str, human: str, ai: str) -> list[dict[str, str]]:
        import psycopg
        new_turns = [
            {"role": "human", "content": human},
            {"role": "ai", "content": ai},
        ]
        with psycopg.connect(self._conninfo) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT messages FROM sessions WHERE session_id = %s",
                    (session_id,),
                )
                row = cur.fetchone()
                messages = row[0] if row else []
                messages.extend(new_turns)
                messages = messages[-(self.k * 2) :]
                
                cur.execute(
                    """
                    INSERT INTO sessions (session_id, messages, updated_at)
                    VALUES (%s, %s, now())
                    ON CONFLICT (session_id) DO UPDATE
                    SET messages = EXCLUDED.messages, updated_at = now()
                    """,
                    (session_id, json.dumps(messages)),
                )
            conn.commit()
        return messages

    def search_query(self, session_id: str, query: str) -> str:
        messages = self.load(session_id)
        prior = ""
        for message in reversed(messages):
            if message.get("role") == "human":
                prior = (message.get("content") or "").strip()
                break
        if prior and prior.lower() != query.strip().lower():
            return f"{prior} {query.strip()}".strip()
        return query.strip()
