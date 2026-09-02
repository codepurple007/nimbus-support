from nimbus_support.tickets import TicketStore


def test_ticket_ids_increment(tmp_path) -> None:
    store = TicketStore(tmp_path / "tickets.json")
    first = store.create(query="weather", route="out_of_scope", retrieved_slugs=[])
    second = store.create(query="human", route="wants_human", retrieved_slugs=[])
    assert first.id == "NIM-0001"
    assert second.id == "NIM-0002"
    assert [row.id for row in store.list_open()] == ["NIM-0001", "NIM-0002"]
    assert first.summary


def test_refund_ticket_starts_pending_and_human_can_approve(tmp_path) -> None:
    store = TicketStore(tmp_path / "tickets.json")
    ticket = store.create(query="refund me", route="refund_request", retrieved_slugs=[])
    assert ticket.status == "pending_approval"
    approved = store.apply_action(ticket.id, "approve_refund")
    assert approved.status == "approved"
    assert store.list_open() == []
    assert store.get(ticket.id).notes[-1]["action"] == "approve_refund"


def test_cannot_approve_a_non_refund_ticket(tmp_path) -> None:
    store = TicketStore(tmp_path / "tickets.json")
    ticket = store.create(query="weather", route="out_of_scope", retrieved_slugs=[])
    try:
        store.apply_action(ticket.id, "approve_refund")
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


def test_resolve_closes_open_ticket(tmp_path) -> None:
    store = TicketStore(tmp_path / "tickets.json")
    ticket = store.create(query="human", route="wants_human", retrieved_slugs=[])
    closed = store.apply_action(ticket.id, "resolve")
    assert closed.status == "resolved"
    assert store.list_open() == []
