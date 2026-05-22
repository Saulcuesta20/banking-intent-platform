from __future__ import annotations

from pathlib import Path
from textwrap import indent

import typer
from rich.console import Console
from app.factory import build_ingestion_provider, build_intent_service

console = Console()
app = typer.Typer()


@app.command()
def ask(
    question: str,
    trace: bool = typer.Option(True, "--trace/--no-trace", help="Print component resolution steps."),
    full_result: bool = typer.Option(False, "--full-result", help="Print the full result payload."),
) -> None:
    """Ask a banking question using the configured intent service."""
    important_trace_prefixes = (
        "matched_records=",
        "candidate_flows=",
        "provider=",
        "cypher_rows=",
        "selected flow=",
        "answer can_resolve=",
        "reason=",
        "business_event=",
        "requires_human_approval=",
        "file=",
        "cannot_resolve=",
    )

    def print_trace(component: str, message: str) -> None:
        if not any(message.startswith(prefix) for prefix in important_trace_prefixes):
            return
        if component in {"llm", "graph"} and (" preview=" in message or "cypher=" in message):
            key, value = message.split("=", 1)
            console.print(f"[bold cyan]{component}[/bold cyan] {key}=")
            console.print(indent(value, "  "))
            return
        console.print(f"[bold cyan]{component}[/bold cyan] {message}")

    if trace:
        console.print("[bold]Banking Intent trace[/bold]")
    try:
        result = build_intent_service().resolve(question, trace=print_trace if trace else None)
    except RuntimeError as exc:
        console.print(f"[bold red]Error[/bold red] {exc}")
        raise typer.Exit(1) from exc
    if trace:
        if result.intent == "unknown":
            console.print("[bold red]Resolution[/bold red] No pude resolver esta pregunta con los flows actuales.")
        else:
            console.print("[bold green]Resolution[/bold green] Pude resolver la pregunta con el registry actual.")
    if full_result or not trace:
        console.print(result.to_dict())
        return

    payload = result.to_dict()
    console.print(
        {
            "can_resolve": payload["can_resolve"],
            "intent": payload["intent"],
            "flow_id": payload["flow_id"],
            "confidence": payload["confidence"],
            "business_event": payload["business_event"],
            "requires_human_approval": payload["requires_human_approval"],
            "plan_steps": len(payload["plan"]),
            "tasks": len(payload["tasks"]),
            "actions": len(payload["related_capabilities"]),
            "ontology_nodes": len(payload["related_ontology_nodes"]),
        }
    )


@app.command()
def ingest(source: Path) -> None:
    """Ingest knowledge files from a local path into the knowledge index."""
    ingestion = build_ingestion_provider()
    records = ingestion.ingest(source)
    console.print_json(
        data={
            "status": "ok",
            "source": str(source),
            "records_ingested": len(records),
            "intents": [record.intent for record in records],
        }
    )


@app.command()
def serve(host: str = "0.0.0.0", port: int = 8000) -> None:
    """Start the FastAPI server."""
    try:
        import uvicorn
    except ImportError as exc:
        raise RuntimeError("uvicorn is required to run the API server.") from exc
    from app.api import create_app

    uvicorn.run(create_app(), host=host, port=port)
