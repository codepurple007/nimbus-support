from nimbus_support.graph.state import AgentState
from nimbus_support.memory import WindowBufferStore


def load_memory_node(state: AgentState, store: WindowBufferStore) -> dict:
    """n8n Simple Memory → agent: load the window before retrieve/generate."""
    session_id = (state.get("session_id") or "default").strip() or "default"
    query = state.get("query") or ""
    messages = store.load(session_id)
    return {
        "session_id": session_id,
        "messages": messages,
        "search_query": store.search_query(session_id, query),
    }


def save_memory_node(state: AgentState, store: WindowBufferStore) -> dict:
    """Append this turn. Window length is enforced in the store (n8n ``k``)."""
    session_id = (state.get("session_id") or "default").strip() or "default"
    query = (state.get("query") or "").strip()
    answer = (state.get("answer") or "").strip()
    if not query or not answer:
        return {}
    messages = store.append(session_id, query, answer)
    return {"messages": messages, "session_id": session_id}
