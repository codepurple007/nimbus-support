from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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


class TicketStore:
    """JSON file of tickets. Optional sink copies the row to Zendesk or similar."""

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
        remote_id = ""
        if self.sink is not None:
            try:
                remote_id = self.sink.publish(ticket) or ""
            except Exception:
                remote_id = ""
        if remote_id:
            ticket = Ticket(**{**asdict(ticket), "remote_id": remote_id})
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
            current = self._from_row(row)
            if action == "approve_refund":
                if current.route != "refund_request":
                    raise ValueError("Only refund_request tickets can be approved.")
                if current.status not in {"pending_approval", "open"}:
                    raise ValueError("Ticket is not waiting for approval.")
                row["status"] = "approved"
                body = note or "Human approved. Stripe is not connected; no money was sent."
            elif action == "deny_refund":
                if current.route != "refund_request":
                    raise ValueError("Only refund_request tickets can be denied.")
                row["status"] = "denied"
                body = note or "Human denied the refund request."
            elif action == "resolve":
                row["status"] = "resolved"
                body = note or "Human resolved this ticket."
            else:
                body = note.strip()
                if not body:
                    raise ValueError("note is required")
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
        return Ticket(
            id=row["id"],
            query=row["query"],
            route=row["route"],
            retrieved_slugs=row.get("retrieved_slugs") or [],
            status=row.get("status") or "open",
            created_at=row.get("created_at") or "",
            session_id=row.get("session_id") or "",
            transcript=row.get("transcript") or [],
            summary=row.get("summary") or "",
            notes=row.get("notes") or [],
            remote_id=row.get("remote_id") or "",
        )

    def _load(self) -> dict:
        if not self.path.exists():
            return {"next_id": 1, "tickets": []}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _save(self, payload: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def make_ticket_store(settings=None) -> TicketStore:
    from nimbus_support.config import get_settings
    from nimbus_support.zendesk import sink_from_settings

    settings = settings or get_settings()
    return TicketStore(settings.tickets_path, sink=sink_from_settings(settings))

