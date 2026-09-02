from nimbus_support.graph.state import AgentState
from nimbus_support.tickets import TicketStore

ROUTES_THAT_FILE = frozenset(
    {"out_of_scope", "jailbreak", "wants_human", "refund_request"}
)


def ticket_node(state: AgentState, store: TicketStore) -> dict:
    """Writes a real ticket. The LLM does not invent the id."""
    route = state.get("route") or ""
    if route not in ROUTES_THAT_FILE:
        return {}
    slugs = [chunk.get("slug", "") for chunk in (state.get("chunks") or [])]
    ticket = store.create(
        query=state.get("query", ""),
        route=route,
        retrieved_slugs=[slug for slug in slugs if slug],
        session_id=state.get("session_id") or "",
        transcript=list(state.get("messages") or []),
    )
    answer = (state.get("answer") or "").rstrip()
    note = f"I opened ticket {ticket.id} for a human. Status: open."
    return {
        "ticket_id": ticket.id,
        "answer": f"{answer}\n\n{note}" if answer else note,
    }
