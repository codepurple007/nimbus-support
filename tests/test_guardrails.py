from nimbus_support.graph.guardrails import (
    IDENTITY_REPLY,
    OUT_OF_SCOPE_REPLY,
    guardrails_node,
)


def test_identity_drops_retrieved_citations() -> None:
    result = guardrails_node(
        {
            "route": "identity",
            "chunks": [{"slug": "refund-policy"}],
            "citations": [
                {"slug": "refund-policy", "title": "Refund policy", "score": 0.2}
            ],
            "draft": "should not appear",
        }
    )
    assert result["answer"] == IDENTITY_REPLY
    assert result["citations"] == []


def test_grounded_keeps_only_cited_slugs() -> None:
    result = guardrails_node(
        {
            "route": "grounded",
            "draft": "Reset via Forgot password.",
            "cited_slugs": ["password-reset"],
            "chunks": [{"slug": "password-reset"}, {"slug": "refund-policy"}],
            "citations": [
                {"slug": "password-reset", "title": "Reset"},
                {"slug": "refund-policy", "title": "Refund"},
            ],
        }
    )
    assert result["route"] == "grounded"
    assert [item["slug"] for item in result["citations"]] == ["password-reset"]


def test_hallucinated_citation_becomes_out_of_scope() -> None:
    result = guardrails_node(
        {
            "route": "grounded",
            "draft": "secret doc",
            "cited_slugs": ["not-in-index"],
            "chunks": [{"slug": "password-reset"}],
            "citations": [{"slug": "password-reset", "title": "Reset"}],
        }
    )
    assert result["route"] == "out_of_scope"
    assert result["answer"] == OUT_OF_SCOPE_REPLY
    assert result["citations"] == []
