from functools import partial

from langgraph.graph import END, START, StateGraph

from nimbus_support.config import get_settings
from nimbus_support.graph.gate import gate_node, route_after_gate
from nimbus_support.graph.generate import LLMClient, generate_node
from nimbus_support.graph.guardrails import guardrails_node
from nimbus_support.graph.lookup import lookup_order_node
from nimbus_support.graph.memory_nodes import load_memory_node, save_memory_node
from nimbus_support.graph.nodes import retrieve_node
from nimbus_support.graph.state import AgentState
from nimbus_support.graph.ticket import ticket_node
from nimbus_support.kb.protocol import Retriever
from nimbus_support.memory import WindowBufferStore
from nimbus_support.orders import OrderStore
from nimbus_support.tickets import TicketStore


def build_graph(
    retriever: Retriever,
    llm: LLMClient | None = None,
    tickets: TicketStore | None = None,
    memory: WindowBufferStore | None = None,
    orders: OrderStore | None = None,
):
    """START → load_memory → retrieve → lookup_order → gate → generate? → guardrails → ticket → save_memory → END."""
    settings = get_settings()
    store = tickets or TicketStore(settings.tickets_path)
    buffer = memory or WindowBufferStore(
        settings.sessions_path, k=settings.context_window_length
    )
    order_store = orders or OrderStore(settings.orders_path)

    graph = StateGraph(AgentState)
    graph.add_node("load_memory", partial(load_memory_node, store=buffer))
    graph.add_node("retrieve", partial(retrieve_node, retriever=retriever))
    graph.add_node("lookup_order", partial(lookup_order_node, store=order_store))
    graph.add_node("gate", gate_node)
    graph.add_node("generate", _make_generate(llm))
    graph.add_node("guardrails", guardrails_node)
    graph.add_node("ticket", partial(ticket_node, store=store))
    graph.add_node("save_memory", partial(save_memory_node, store=buffer))

    graph.add_edge(START, "load_memory")
    graph.add_edge("load_memory", "retrieve")
    graph.add_edge("retrieve", "lookup_order")
    graph.add_edge("lookup_order", "gate")
    graph.add_conditional_edges(
        "gate",
        route_after_gate,
        {"generate": "generate", "guardrails": "guardrails"},
    )
    graph.add_edge("generate", "guardrails")
    graph.add_edge("guardrails", "ticket")
    graph.add_edge("ticket", "save_memory")
    graph.add_edge("save_memory", END)
    return graph.compile()


def _make_generate(llm: LLMClient | None):
    def _generate(state: AgentState) -> dict:
        if llm is None:
            raise RuntimeError(
                "generate ran but no LLM was configured. "
                "Put GEMINI_API_KEY in the file named .env (not .env.example), "
                "then run: python -m nimbus_support ask \"How do I reset my password?\""
            )
        return generate_node(state, llm)

    return _generate
