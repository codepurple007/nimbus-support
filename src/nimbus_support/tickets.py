from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

OPEN_STATUSES = frozenset({"open", "pending_approval"})
ACTIONS = frozenset({"resolve", "approve_refund", "deny_refund", "note"})


@dataclass(frozen=True)
class Ticket:
    id: str
    query: str
    route: str
    retrieved_slugs: list[str]
    status: str
    created_at: str
    session_id: str = ""
    transcript: list[dict] = field(default_factory=list)
    summary: str = ""
    notes: list[dict[str, str]] = field(default_factory=list)
    remote_id: str = ""


class TicketStore(Protocol):
    def create(self, **kwargs) -> Ticket: ...
    def get(self, ticket_id: str) -> Ticket | None: ...
    def list_all(self) -> list[Ticket]: ...
    def list_open(self) -> list[Ticket]: ...
    def apply_action(self, ticket_id: str, action: str, note: str = "") -> Ticket: ...


def summarize_ticket(query: str, route: str, transcript: list[dict] | None) -> str:
    preview = (query or "").strip().replace("\n", " ")[:160]
    turns = len(transcript or [])
    labels = {
        "refund_request": "Refund action queued. Agent did not send money.",
        "wants_human": "Customer asked for a human.",
        "jailbreak": "Jailbreak or policy-bypass attempt.",
        "out_of_scope": "No help-center answer. Escalated.",
    }
    why = labels.get(route, route.replace("_", " "))
    return f"{why} Latest: {preview} Session turns on file: {turns}."


def _status_for_route(route: str) -> str:
    if route == "refund_request":
        return "pending_approval"
    return "open"


class JsonTicketStore:
    """JSON file of tickets."""

    def __init__(self, path: Path, sink: Any | None = None) -> None:
        self.path = path
        self.sink = sink

    def create(
        self,
        *,
        query: str,
        route: str,
        retrieved_slugs: list[str],
        session_id: str = "",
        transcript: list[dict] | None = None,
        status: str | None = None,
    ) -> Ticket:
        payload = self._load()
        number = payload["next_id"]
        turns = list(transcript or [])
        ticket = Ticket(
            id=f"NIM-{number:04d}",
            query=query,
            route=route,
            retrieved_slugs=retrieved_slugs,
            status=status or _status_for_route(route),
            created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            session_id=session_id,
            transcript=turns,
            summary=summarize_ticket(query, route, turns),
        )
        payload["next_id"] = number + 1
        payload["tickets"].append(asdict(ticket))
        self._save(payload)
        return ticket

    def get(self, ticket_id: str) -> Ticket | None:
        for row in self._load()["tickets"]:
            if row.get("id") == ticket_id:
                return self._from_row(row)
        return None

    def list_all(self) -> list[Ticket]:
        return [self._from_row(row) for row in self._load()["tickets"]]

    def list_open(self) -> list[Ticket]:
        return [row for row in self.list_all() if row.status in OPEN_STATUSES]

    def apply_action(self, ticket_id: str, action: str, note: str = "") -> Ticket:
        action = (action or "").strip().lower()
        if action not in ACTIONS:
            raise ValueError(f"Unknown action: {action}")
        payload = self._load()
        for row in payload["tickets"]:
            if row.get("id") != ticket_id:
                continue
            if action == "approve_refund":
                row["status"] = "approved"
                body = note or "Approved."
            elif action == "deny_refund":
                row["status"] = "denied"
                body = note or "Denied."
            elif action == "resolve":
                row["status"] = "resolved"
                body = note or "Resolved."
            else:
                body = note.strip()
            row.setdefault("notes", []).append(
                {
                    "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "action": action,
                    "body": body,
                }
            )
            self._save(payload)
            return self._from_row(row)
        raise KeyError(ticket_id)

    def _from_row(self, row: dict) -> Ticket:
        return Ticket(**row)

    def _load(self) -> dict:
        if not self.path.exists():
            return {"next_id": 1, "tickets": []}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"next_id": 1, "tickets": []}

    def _save(self, payload: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


class PgTicketStore:
    """PostgreSQL ticket store implementation."""

    def __init__(self, conninfo: str) -> None:
        self._conninfo = conninfo

    def create(
        self,
        *,
        query: str,
        route: str,
        retrieved_slugs: list[str],
        session_id: str = "",
        transcript: list[dict] | None = None,
        status: str | None = None,
    ) -> Ticket:
        import psycopg
        turns = list(transcript or [])
        status = status or _status_for_route(route)
        summary = summarize_ticket(query, route, turns)
        
        with psycopg.connect(self._conninfo) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM tickets")
                count = cur.fetchone()[0]
                ticket_id = f"NIM-{count + 1:04d}"
                
                cur.execute(
                    """
                    INSERT INTO tickets (id, query, route, status, session_id, transcript, summary, retrieved_slugs)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING created_at
                    """,
                    (ticket_id, query, route, status, session_id, json.dumps(turns), summary, retrieved_slugs),
                )
                created_at = cur.fetchone()[0].isoformat()
            conn.commit()
            
        return Ticket(
            id=ticket_id,
            query=query,
            route=route,
            retrieved_slugs=retrieved_slugs,
            status=status,
            created_at=created_at,
            session_id=session_id,
            transcript=turns,
            summary=summary,
        )

    def get(self, ticket_id: str) -> Ticket | None:
        import psycopg
        with psycopg.connect(self._conninfo) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM tickets WHERE id = %s", (ticket_id,))
                row = cur.fetchone()
                if not row:
                    return None
                return self._from_row(cur, row)

    def list_all(self) -> list[Ticket]:
        import psycopg
        with psycopg.connect(self._conninfo) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM tickets ORDER BY created_at DESC")
                return [self._from_row(cur, row) for row in cur.fetchall()]

    def list_open(self) -> list[Ticket]:
        import psycopg
        with psycopg.connect(self._conninfo) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM tickets WHERE status IN %s ORDER BY created_at DESC",
                    (tuple(OPEN_STATUSES),),
                )
                return [self._from_row(cur, row) for row in cur.fetchall()]

    def apply_action(self, ticket_id: str, action: str, note: str = "") -> Ticket:
        import psycopg
        action = (action or "").strip().lower()
        if action not in ACTIONS:
            raise ValueError(f"Unknown action: {action}")
            
        with psycopg.connect(self._conninfo) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT route, status, notes FROM tickets WHERE id = %s", (ticket_id,))
                row = cur.fetchone()
                if not row:
                    raise KeyError(ticket_id)
                
                route, status, notes = row
                new_status = status
                if action == "approve_refund":
                    new_status = "approved"
                    body = note or "Approved."
                elif action == "deny_refund":
                    new_status = "denied"
                    body = note or "Denied."
                elif action == "resolve":
                    new_status = "resolved"
                    body = note or "Resolved."
                else:
                    body = note.strip()
                
                notes.append({
                    "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "action": action,
                    "body": body,
                })
                
                cur.execute(
                    "UPDATE tickets SET status = %s, notes = %s WHERE id = %s",
                    (new_status, json.dumps(notes), ticket_id),
                )
            conn.commit()
        return self.get(ticket_id)

    def _from_row(self, cur, row: tuple) -> Ticket:
        cols = [d[0] for d in cur.description]
        data = dict(zip(cols, row))
        if isinstance(data["created_at"], datetime):
            data["created_at"] = data["created_at"].isoformat()
        return Ticket(**data)


def make_ticket_store(settings=None) -> TicketStore:
    from nimbus_support.config import get_settings
    settings = settings or get_settings()
    if settings.retrieval_backend == "pgvector":
        return PgTicketStore(settings.database_url)
    return JsonTicketStore(settings.tickets_path)
