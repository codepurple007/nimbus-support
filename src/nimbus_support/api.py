from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from nimbus_support.config import get_settings
from nimbus_support.connectors.sync import sync_connectors
from nimbus_support.connectors.urls import ingest_url
from nimbus_support.graph.builder import build_graph
from nimbus_support.graph.generate import make_llm_client
from nimbus_support.kb.ingest import ingest_help_center
from nimbus_support.kb.retrieve import load_retriever
from nimbus_support.memory import WindowBufferStore
from nimbus_support.orders import OrderStore
from nimbus_support.pii import redact
from nimbus_support.tickets import Ticket, TicketStore, make_ticket_store
from nimbus_support.tracing import flush, observation

WEB_DIR = Path(__file__).resolve().parent / "web"


class ChatBody(BaseModel):
    """n8n Chat Trigger webhook body (sessionId + chatInput + optional action)."""

    sessionId: str = Field(default="web", min_length=1)
    chatInput: str = ""
    action: str | None = None


class IngestUrlBody(BaseModel):
    url: str = Field(min_length=8)


class TicketActionBody(BaseModel):
    action: str
    note: str = ""


@dataclass
class Runtime:
    graph: object
    memory: WindowBufferStore
    tickets: TicketStore


def build_runtime() -> Runtime:
    settings = get_settings()
    retriever = load_retriever(settings=settings)
    llm = make_llm_client(settings)
    memory = WindowBufferStore(settings.sessions_path, k=settings.context_window_length)
    tickets = make_ticket_store(settings)
    graph = build_graph(
        retriever,
        llm=llm,
        tickets=tickets,
        memory=memory,
        orders=OrderStore(settings.orders_path),
    )
    return Runtime(graph=graph, memory=memory, tickets=tickets)


def create_app(runtime: Runtime | None = None) -> FastAPI:
    api = FastAPI(title="Nimbus support")
    api.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:3000", "http://localhost:3000"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    holder: dict[str, Runtime] = {}

    def current() -> Runtime:
        if runtime is not None:
            return runtime
        if "rt" not in holder:
            holder["rt"] = build_runtime()
        return holder["rt"]

    def reload_index() -> None:
        holder.pop("rt", None)

    def require_admin(authorization: str | None = Header(default=None)) -> None:
        token = get_settings().admin_token
        if not token:
            return
        if authorization != f"Bearer {token}":
            raise HTTPException(401, "Admin token required")

    @api.get("/")
    def chat_page():
        page = WEB_DIR / "index.html"
        if not page.exists():
            raise HTTPException(404, "chat page missing")
        return FileResponse(page)

    @api.post("/chat")
    def chat(body: ChatBody):
        rt = current()
        if body.action == "loadPreviousSession":
            return {"data": rt.memory.load(body.sessionId)}
        query = (body.chatInput or "").strip()
        if not query:
            raise HTTPException(400, "chatInput is required")
        try:
            with observation("nimbus.ask", input={"query": redact(query)}):
                result = rt.graph.invoke({"query": query, "session_id": body.sessionId})
            flush()
        except Exception as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return _chat_payload(result, body.sessionId)

    @api.post("/chat/stream")
    def chat_stream(body: ChatBody):
        rt = current()
        if body.action == "loadPreviousSession":
            raise HTTPException(400, "Use POST /chat for loadPreviousSession")
        query = (body.chatInput or "").strip()
        if not query:
            raise HTTPException(400, "chatInput is required")

        def events():
            try:
                with observation("nimbus.ask", input={"query": redact(query)}):
                    last = {"query": query, "session_id": body.sessionId}
                    for update in rt.graph.stream(dict(last), stream_mode="updates"):
                        node = next(iter(update))
                        delta = update[node]
                        if isinstance(delta, dict):
                            last.update(delta)
                        yield _sse(
                            "node",
                            {"node": node, "route": last.get("route")},
                        )
                flush()
            except Exception as exc:
                yield _sse("error", {"detail": str(exc)})
                return
            yield _sse("done", _chat_payload(last, body.sessionId))

        return StreamingResponse(events(), media_type="text/event-stream")

    @api.get("/api/tickets")
    def list_tickets(include_closed: bool = Query(default=False, alias="all")):
        rows = current().tickets.list_all() if include_closed else current().tickets.list_open()
        return [_ticket_json(row) for row in rows]

    @api.get("/api/tickets/{ticket_id}")
    def get_ticket(ticket_id: str):
        row = current().tickets.get(ticket_id)
        if row is None:
            raise HTTPException(404, "Ticket not found")
        return _ticket_json(row, detail=True)

    @api.post("/api/tickets/{ticket_id}/actions")
    def ticket_action(
        ticket_id: str,
        body: TicketActionBody,
        _: None = Depends(require_admin),
    ):
        try:
            row = current().tickets.apply_action(ticket_id, body.action, body.note)
        except KeyError:
            raise HTTPException(404, "Ticket not found") from None
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        return _ticket_json(row, detail=True)

    @api.post("/api/ingest")
    async def ingest_upload(
        file: UploadFile = File(...),
        _: None = Depends(require_admin),
    ):
        settings = get_settings()
        name = Path(file.filename or "upload").name
        suffix = Path(name).suffix.lower()
        if suffix not in {".md", ".csv", ".pdf"}:
            raise HTTPException(400, "Only .md, .csv, and .pdf are ingested.")
        dest_dir = settings.help_center_dir / "connected"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / name
        dest.write_bytes(await file.read())
        chunks = ingest_help_center(settings)
        reload_index()
        return {"indexed": len(chunks), "file": name}

    @api.post("/api/ingest-url")
    def ingest_from_url(body: IngestUrlBody, _: None = Depends(require_admin)):
        settings = get_settings()
        dest = settings.help_center_dir / "connected"
        try:
            path = ingest_url(body.url, dest)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        chunks = ingest_help_center(settings)
        reload_index()
        return {"indexed": len(chunks), "file": path.name}

    @api.post("/api/sync")
    def sync_knowledge(_: None = Depends(require_admin)):
        settings = get_settings()
        written = sync_connectors(settings)
        chunks = ingest_help_center(settings)
        reload_index()
        return {"copied": [path.name for path in written], "indexed": len(chunks)}

    return api


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _chat_payload(result: dict, session_id: str) -> dict:
    return {
        "output": result.get("answer") or "",
        "sessionId": session_id,
        "route": result.get("route"),
        "citations": result.get("citations") or [],
        "ticket_id": result.get("ticket_id") or None,
    }


def _ticket_json(row: Ticket, *, detail: bool = False) -> dict:
    data = {
        "id": row.id,
        "status": row.status,
        "route": row.route,
        "query": row.query,
        "created_at": row.created_at,
        "session_id": row.session_id,
        "summary": row.summary,
        "remote_id": row.remote_id or None,
    }
    if detail:
        data["transcript"] = row.transcript
        data["notes"] = row.notes
        data["retrieved_slugs"] = row.retrieved_slugs
    return data


app = create_app()
