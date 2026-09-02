from nimbus_support.tickets import Ticket, TicketStore
from nimbus_support.zendesk import ZendeskSink


def test_zendesk_sink_posts_ticket_payload() -> None:
    captured = {}

    def poster(url, body, headers):
        captured["url"] = url
        captured["body"] = body
        return {"ticket": {"id": 99}}

    sink = ZendeskSink(
        subdomain="nimbus",
        email="agent@nimbus.example",
        api_token="secret",
        poster=poster,
    )
    ticket = Ticket(
        id="NIM-0001",
        query="refund me ada@nimbus.example",
        route="refund_request",
        retrieved_slugs=[],
        status="pending_approval",
        created_at="2026-09-02T00:00:00+00:00",
        summary="Refund action queued.",
    )
    remote = sink.publish(ticket)
    assert remote == "99"
    assert captured["url"] == "https://nimbus.zendesk.com/api/v2/tickets.json"
    assert "ada@nimbus.example" not in captured["body"]["ticket"]["comment"]["body"]
    assert "NIM-0001" in captured["body"]["ticket"]["subject"]


def test_ticket_store_records_remote_id(tmp_path) -> None:
    sink = ZendeskSink(
        subdomain="nimbus",
        email="agent@nimbus.example",
        api_token="secret",
        poster=lambda url, body, headers: {"ticket": {"id": 7}},
    )
    store = TicketStore(tmp_path / "tickets.json", sink=sink)
    ticket = store.create(query="hello", route="wants_human", retrieved_slugs=[])
    assert ticket.remote_id == "7"
    assert store.get(ticket.id).remote_id == "7"
