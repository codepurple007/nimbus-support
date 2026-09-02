from __future__ import annotations

import typer

from nimbus_support.config import get_settings
from nimbus_support.connectors.sync import sync_connectors
from nimbus_support.graph.builder import build_graph
from nimbus_support.graph.generate import list_gemini_models, make_llm_client
from nimbus_support.kb.ingest import ingest_help_center
from nimbus_support.kb.retrieve import load_retriever
from nimbus_support.memory import WindowBufferStore
from nimbus_support.orders import OrderStore
from nimbus_support.pii import redact
from nimbus_support.tickets import TicketStore, make_ticket_store
from nimbus_support.tracing import flush, observation

app = typer.Typer(no_args_is_help=True, add_completion=False)


@app.command()
def ingest() -> None:
    """Sync connectors, chunk the help center, and build the local index."""
    chunks = ingest_help_center()
    settings = get_settings()
    typer.echo(
        f"Indexed {len(chunks)} chunks "
        f"backend={settings.retrieval_backend} → {settings.index_dir}"
    )


@app.command("sync")
def sync() -> None:
    """Copy Drive/Sheets connector files into the help center, then ingest."""
    written = sync_connectors()
    chunks = ingest_help_center()
    typer.echo(f"Copied {len(written)} files, indexed {len(chunks)} chunks.")
    for path in written:
        typer.echo(f"  {path.name}")


@app.command()
def search(query: str, k: int = 4) -> None:
    """Search the index (same retrieve node the graph uses)."""
    retriever = load_retriever(settings=get_settings())
    hits = retriever.search(query, k=k)
    if not hits:
        typer.echo("No hits.")
        raise typer.Exit(code=1)
    for rank, hit in enumerate(hits, start=1):
        typer.echo(
            f"{rank}. {hit.chunk.article_slug}  score={hit.score:.3f}\n"
            f"   {hit.chunk.content[:220]}\n"
        )


@app.command("models")
def models() -> None:
    """Print Gemini model ids this API key can call. Copy one into GEMINI_CHAT_MODEL."""
    for name in list_gemini_models():
        typer.echo(name)


@app.command()
def ask(
    query: str,
    session: str = typer.Option(
        "cli",
        "--session",
        help="Session id (n8n Chat Trigger sessionId). Same id = same memory window.",
    ),
) -> None:
    """Product path: load_memory → retrieve → gate → generate? → ticket → save_memory."""
    settings = get_settings()
    retriever = load_retriever(settings=settings)
    llm = make_llm_client(settings)
    graph = _graph(retriever, llm, settings)
    with observation("nimbus.ask", input={"query": redact(query)}):
        result = graph.invoke({"query": query, "session_id": session})
    flush()
    typer.echo(result.get("answer") or "")
    if result.get("route") == "grounded":
        for citation in result.get("citations") or []:
            typer.echo(f"  source: {citation['slug']}")
    typer.echo(f"[{result.get('route')}]")
    if result.get("ticket_id"):
        typer.echo(f"ticket: {result['ticket_id']}")


@app.command()
def tickets(
    include_closed: bool = typer.Option(False, "--all"),
) -> None:
    """List tickets the agent actually filed (not search hits)."""
    store = TicketStore(get_settings().tickets_path)
    rows = store.list_all() if include_closed else store.list_open()
    if not rows:
        typer.echo("No tickets.")
        raise typer.Exit(code=0)
    for row in rows:
        typer.echo(f"{row.id}  {row.status}  {row.route}  {row.query[:80]}")
        if row.summary:
            typer.echo(f"    {row.summary}")


@app.command("ticket")
def ticket_cmd(
    ticket_id: str,
    action: str = typer.Argument(help="resolve | approve_refund | deny_refund | note"),
    note: str = typer.Option("", "--note"),
) -> None:
    """Human inbox action. Approving a refund does not send money."""
    store = TicketStore(get_settings().tickets_path)
    try:
        row = store.apply_action(ticket_id, action, note)
    except (KeyError, ValueError) as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc
    typer.echo(f"{row.id}  {row.status}  {row.route}")


@app.command()
def serve(host: str = "127.0.0.1", port: int = 8080) -> None:
    """Hosted chat — same contract as n8n Chat Trigger (sessionId + chatInput)."""
    import uvicorn

    uvicorn.run(
        "nimbus_support.api:app",
        host=host,
        port=port,
        reload=False,
    )


def _graph(retriever, llm, settings):
    return build_graph(
        retriever,
        llm=llm,
        tickets=make_ticket_store(settings),
        memory=WindowBufferStore(
            settings.sessions_path, k=settings.context_window_length
        ),
        orders=OrderStore(settings.orders_path),
    )


def main() -> None:
    app()


if __name__ == "__main__":
    main()
