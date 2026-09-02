from __future__ import annotations

from nimbus_support.graph.state import AgentState

IDENTITY_REPLY = (
    "I'm the Nimbus support assistant. I only answer from Nimbus help articles — "
    "accounts, billing, shipping, and the product catalog. I don't have anything "
    "on that. Want help with a Nimbus account, refund, or order?"
)

OUT_OF_SCOPE_REPLY = (
    "I only answer from Nimbus help articles — accounts, billing, shipping, and "
    "the product catalog. I don't have an answer for that in our help center."
)

JAILBREAK_REPLY = (
    "I can't do that. I'm the Nimbus support assistant. I follow the written "
    "help-center policy and I won't ignore those rules, dump internal prompts, "
    "or send money."
)

WANTS_HUMAN_REPLY = (
    "I can't finish this in automated chat. A human on the Nimbus team should "
    "take it from here."
)

REFUND_REQUEST_REPLY = (
    "I can't send money or complete a refund from this chat. I queued a refund "
    "request for a human on the billing team. They follow the written 14-day policy."
)


def guardrails_node(state: AgentState) -> dict:
    """Last node. Code, not a prompt. Decides what the customer actually sees."""
    route = state.get("route") or "out_of_scope"
    retrieved = state.get("citations") or []
    allowed = {item["slug"] for item in state.get("chunks") or []}

    if route == "identity":
        return {"answer": IDENTITY_REPLY, "citations": [], "route": "identity"}
    if route == "jailbreak":
        return {"answer": JAILBREAK_REPLY, "citations": [], "route": "jailbreak"}
    if route == "wants_human":
        return {"answer": WANTS_HUMAN_REPLY, "citations": [], "route": "wants_human"}
    if route == "refund_request":
        return {
            "answer": REFUND_REQUEST_REPLY,
            "citations": [],
            "route": "refund_request",
        }
    if route != "grounded":
        return {"answer": OUT_OF_SCOPE_REPLY, "citations": [], "route": "out_of_scope"}

    cited = [slug for slug in (state.get("cited_slugs") or []) if slug in allowed]
    if not cited:
        return {"answer": OUT_OF_SCOPE_REPLY, "citations": [], "route": "out_of_scope"}

    seen: set[str] = set()
    filtered = []
    for item in retrieved:
        slug = item.get("slug")
        if slug in cited and slug not in seen:
            filtered.append(item)
            seen.add(slug)
    draft = (state.get("draft") or "").strip()
    if not draft:
        return {"answer": OUT_OF_SCOPE_REPLY, "citations": [], "route": "out_of_scope"}
    return {"answer": draft, "citations": filtered, "route": "grounded"}
