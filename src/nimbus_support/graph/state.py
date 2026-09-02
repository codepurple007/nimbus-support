from typing import Any, Literal, TypedDict

Route = Literal[
    "needs_generate",
    "grounded",
    "identity",
    "out_of_scope",
    "jailbreak",
    "wants_human",
    "refund_request",
]


class AgentState(TypedDict, total=False):
    """Working memory for one graph invoke."""

    query: str
    session_id: str
    search_query: str
    messages: list[dict[str, str]]
    chunks: list[dict[str, Any]]
    citations: list[dict[str, Any]]
    order: dict[str, Any]
    route: Route
    draft: str
    cited_slugs: list[str]
    answer: str
    ticket_id: str
