from nimbus_support.api import Runtime, create_app
from nimbus_support.config import PROJECT_ROOT
from nimbus_support.graph.builder import build_graph
from nimbus_support.graph.generate import GenerateResult
from nimbus_support.kb.chunking import chunk_articles, load_help_center
from nimbus_support.kb.retrieve import TfidfRetriever
from nimbus_support.memory import WindowBufferStore
from nimbus_support.orders import OrderStore
from nimbus_support.tickets import TicketStore
from tests.fakes import ScriptedLLM


def _client(tmp_path, llm=None):
    from fastapi.testclient import TestClient

    articles = load_help_center(PROJECT_ROOT / "data" / "help-center")
    retriever = TfidfRetriever.from_chunks(chunk_articles(articles))
    tickets = TicketStore(tmp_path / "tickets.json")
    memory = WindowBufferStore(tmp_path / "sessions.json", k=5)
    graph = build_graph(
        retriever,
        llm=llm,
        tickets=tickets,
        memory=memory,
        orders=OrderStore(PROJECT_ROOT / "data" / "orders.json"),
    )
    app = create_app(Runtime(graph=graph, memory=memory, tickets=tickets))
    return TestClient(app)


def test_chat_trigger_contract_identity(tmp_path) -> None:
    client = _client(tmp_path, ScriptedLLM(GenerateResult("grounded", "no", [])))
    empty = client.post(
        "/chat", json={"sessionId": "web-1", "action": "loadPreviousSession"}
    )
    assert empty.json()["data"] == []
    res = client.post(
        "/chat", json={"sessionId": "web-1", "chatInput": "what are you"}
    )
    body = res.json()
    assert res.status_code == 200
    assert "output" in body
    assert body["route"] == "identity"
    assert body["ticket_id"] is None
    history = client.post(
        "/chat", json={"sessionId": "web-1", "action": "loadPreviousSession"}
    )
    assert len(history.json()["data"]) == 2


def test_chat_escalate_creates_ticket(tmp_path) -> None:
    client = _client(tmp_path, ScriptedLLM(GenerateResult("grounded", "no", [])))
    res = client.post(
        "/chat",
        json={"sessionId": "web-1", "chatInput": "I want to talk to a human"},
    )
    assert res.json()["ticket_id"] == "NIM-0001"
    inbox = client.get("/api/tickets")
    assert inbox.json()[0]["id"] == "NIM-0001"


def test_hosted_chat_page_exists(tmp_path) -> None:
    client = _client(tmp_path, ScriptedLLM(GenerateResult("grounded", "no", [])))
    res = client.get("/")
    assert res.status_code == 200
    assert b"Nimbus" in res.content


def test_ticket_inbox_has_summary_and_hitl_action(tmp_path) -> None:
    client = _client(tmp_path, ScriptedLLM(GenerateResult("grounded", "no", [])))
    filed = client.post(
        "/chat",
        json={"sessionId": "web-1", "chatInput": "Please process my refund now"},
    )
    ticket_id = filed.json()["ticket_id"]
    detail = client.get(f"/api/tickets/{ticket_id}")
    body = detail.json()
    assert body["status"] == "pending_approval"
    assert body["summary"]
    approved = client.post(
        f"/api/tickets/{ticket_id}/actions",
        json={"action": "approve_refund"},
    )
    assert approved.json()["status"] == "approved"
    inbox = client.get("/api/tickets")
    assert inbox.json() == []


def test_chat_stream_emits_nodes(tmp_path) -> None:
    client = _client(tmp_path, ScriptedLLM(GenerateResult("grounded", "no", [])))
    with client.stream(
        "POST",
        "/chat/stream",
        json={"sessionId": "web-1", "chatInput": "what are you"},
    ) as res:
        text = b"".join(res.iter_bytes()).decode()
    assert "event: node" in text
    assert "event: done" in text
    assert "identity" in text
