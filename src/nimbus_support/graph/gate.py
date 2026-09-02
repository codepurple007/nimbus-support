"""Deterministic pre-LLM gate. Cheap, testable, no tokens."""

from __future__ import annotations

import re

from nimbus_support.graph.state import AgentState, Route

_IDENTITY = re.compile(
    r"\b("
    r"what are you|who are you|what('?s| is) your name|"
    r"are you (a |an )?(bot|ai|chatgpt|llm|language model|assistant)"
    r")\b",
    re.IGNORECASE,
)

_JAILBREAK = re.compile(
    r"("
    r"ignore (all )?(previous|your|all) (instructions|rules)|"
    r"developer mode|system prompt|jailbreak|"
    r"you are now\b|dan mode|"
    r"print (your |the )?(system )?prompt|"
    r"ignore previous instructions"
    r")",
    re.IGNORECASE,
)


_HUMAN = re.compile(
    r"("
    r"talk to (a )?(human|person|agent|someone)|"
    r"speak to (a )?(human|person|agent)|"
    r"real (human|person|agent)|"
    r"(open|create|get|file|make)\s+(me\s+)?(a\s+)?ticket|"
    r"escalate|"
    r"customer service"
    r")",
    re.IGNORECASE,
)

# Action (send money), not a policy question. Phase 3 HITL.
_REFUND_ACTION = re.compile(
    r"("
    r"refund me|"
    r"process (my |a |the )?refund|"
    r"send (me )?(my )?money|"
    r"give me (my )?(money|refund) back|"
    r"pay me\b|"
    r"issue (a |the |my )?refund"
    r")",
    re.IGNORECASE,
)


def is_identity_query(query: str) -> bool:
    return bool(_IDENTITY.search(query.strip()))


def is_jailbreak_query(query: str) -> bool:
    return bool(_JAILBREAK.search(query.strip()))


def is_human_request(query: str) -> bool:
    return bool(_HUMAN.search(query.strip()))


def is_refund_action(query: str) -> bool:
    return bool(_REFUND_ACTION.search(query.strip()))


def gate_node(state: AgentState) -> dict[str, Route]:
    """Runs after retrieve. Retrieve still happened; we decide if the LLM may talk."""
    query = state.get("query", "")
    chunks = state.get("chunks") or []
    if is_jailbreak_query(query):
        return {"route": "jailbreak"}
    if is_refund_action(query):
        return {"route": "refund_request"}
    if is_human_request(query):
        return {"route": "wants_human"}
    if is_identity_query(query):
        return {"route": "identity"}
    if not chunks:
        return {"route": "out_of_scope"}
    return {"route": "needs_generate"}


def route_after_gate(state: AgentState) -> str:
    if state.get("route") == "needs_generate":
        return "generate"
    return "guardrails"
