from nimbus_support.graph.state import AgentState
from nimbus_support.kb.protocol import Retriever
from nimbus_support.tracing import observation


def retrieve_node(state: AgentState, retriever: Retriever, k: int = 4) -> dict:
    """Deterministic. Always runs. The model is not allowed to skip this."""
    query = (state.get("search_query") or state.get("query") or "").strip()
    with observation("retrieve"):
        hits = retriever.search(query, k=k)
    return {
        "chunks": [
            {
                "slug": hit.chunk.article_slug,
                "title": hit.chunk.article_title,
                "source_type": hit.chunk.source_type,
                "content": hit.chunk.content,
                "score": hit.score,
            }
            for hit in hits
        ],
        "citations": [hit.as_citation() for hit in hits],
    }
