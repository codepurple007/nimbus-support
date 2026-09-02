from nimbus_support.graph.state import AgentState
from nimbus_support.orders import OrderStore, extract_order_id


def lookup_order_node(state: AgentState, store: OrderStore) -> dict:
    """Live store lookup. Analog of n8n's HTTP Request tool, not a made-up node."""
    order_id = extract_order_id(state.get("query") or "")
    if not order_id:
        return {}
    record = store.get(order_id)
    if record:
        content = (
            f"Order {order_id} was found in the Nimbus store. "
            + "; ".join(f"{key}={value}" for key, value in record.items() if key != "id")
            + ". Do not invent extra tracking fields."
        )
        slug = f"order-{order_id}"
        title = f"Order {order_id}"
        found = True
    else:
        content = (
            f"No Nimbus order exists with number {order_id}. "
            "Ask the customer to check the number, or open a ticket."
        )
        slug = "order-lookup"
        title = "Order lookup"
        found = False
        record = {"id": order_id, "found": False}

    chunk = {
        "slug": slug,
        "title": title,
        "source_type": "order_lookup",
        "content": content,
        "score": 1.0,
    }
    citation = {
        "slug": slug,
        "title": title,
        "source_path": "orders",
        "score": 1.0,
        "excerpt": content[:240],
    }
    chunks = list(state.get("chunks") or []) + [chunk]
    citations = list(state.get("citations") or []) + [citation]
    order = {**record, "found": found}
    return {"order": order, "chunks": chunks, "citations": citations}
