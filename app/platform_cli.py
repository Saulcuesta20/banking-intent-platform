from __future__ import annotations

import json
import os
import subprocess

import typer
from rich.console import Console
from rich.table import Table

from app.cli import kb as query_knowledge_base
from app.cli import kb_views as show_knowledge_views
from tools.kb_reset_load import reset_load_knowledge_bases

console = Console()
app = typer.Typer(help="Ingest and query knowledge bases.")

ENGINE_SPECS = [
    {
        "name": "neo4j",
        "kind": "graph",
        "database": "neo4j",
        "usage": "Graph relationships, flows, processes, tasks, tools, concepts.",
        "containers": ["banking-intent-neo4j", "banking-intent-platform-neo4j-1"],
        "host_endpoint": "http://localhost:7474 / bolt://localhost:7687",
        "internal_endpoint": "bolt://neo4j:7687",
    },
    {
        "name": "qdrant",
        "kind": "vector",
        "database": "knowledge_assets collection",
        "usage": "Semantic/vector search for text evidence and knowledge assets.",
        "containers": ["banking-intent-platform-qdrant-1"],
        "host_endpoint": "http://localhost:6333",
        "internal_endpoint": "http://qdrant:6333",
    },
    {
        "name": "postgres",
        "kind": "relational",
        "database": "banking_intent",
        "usage": "Runtime state, audit, approvals, and monitoring.",
        "containers": ["banking-intent-platform-postgres-1"],
        "host_endpoint": "postgresql://localhost:5432/banking_intent",
        "internal_endpoint": "postgresql://postgres:5432/banking_intent",
    },
    {
        "name": "redis",
        "kind": "cache",
        "database": "db 0",
        "usage": "Cache/session/work queue support.",
        "containers": ["banking-intent-platform-redis-1"],
        "host_endpoint": "redis://localhost:6379/0",
        "internal_endpoint": "redis://redis:6379/0",
    },
    {
        "name": "app",
        "kind": "api",
        "database": "n/a",
        "usage": "FastAPI application service.",
        "containers": ["banking-intent-app", "banking-intent-platform-app-1"],
        "host_endpoint": "http://localhost:8000",
        "internal_endpoint": "http://app:8000",
    },
]


@app.command("query")
def kb_query(
    engines: bool = typer.Option(False, "--engines", help="Show database engines, status, ports, and endpoints."),
    knowledge_base: str | None = typer.Option(None, "--kb", "--knowledge-base", help="Knowledge base/store: repository, graph, vector, relational, document."),
    owner_kb: str | None = typer.Option(None, "--owner-kb", help="Logical owner KB: process_kb, planning_kb, rules_kb, business_model_kb, qa_kb, document_kb, causality_kb, config_kb."),
    asset_type: str | None = typer.Option(None, "--asset-type", "--asset", help="Asset type, for example flow, process, business_rule, plan, tool."),
    asset_id: str | None = typer.Option(None, "--id", help="Global asset id to inspect."),
    text: str | None = typer.Option(None, "--text", "-q", help="Search text."),
    relation_type: str | None = typer.Option(None, "--relation-type", help="Filter assets that have outbound relationships of this type."),
    store: str = typer.Option("catalog", "--store", help="catalog, document, vector, or all."),
    tree: bool = typer.Option(False, "--tree", help="Include child relationships."),
    limit: int = typer.Option(50, "--limit", help="Maximum rows."),
    status: str = typer.Option("approved", "--status", help="approved, candidate, draft, rejected, deprecated, or all."),
    output_format: str = typer.Option("table", "--format", help="table, tree, or json."),
) -> None:
    """Query KB levels: knowledge base, asset type, or specific asset."""
    if engines:
        _print_engine_status()
        return
    if not any([knowledge_base, owner_kb, asset_type, asset_id, text, relation_type]):
        show_knowledge_views()
        return
    query_knowledge_base(
        knowledge_base=knowledge_base,
        owner_kb=owner_kb,
        requested_asset_type=asset_type,
        asset_id=asset_id,
        query=text,
        relation_type=relation_type,
        store=store,
        tree=tree,
        limit=limit,
        status=status,
        output_format=output_format,
    )


@app.command("start")
def kb_start(
    app_service: bool = typer.Option(False, "--app/--no-app", help="Also start the API app container."),
) -> None:
    """Start local knowledge-base engines without loading data."""
    _start_databases_if_needed(True)
    if app_service:
        env = {**os.environ, "DOCKER_API_VERSION": os.getenv("DOCKER_API_VERSION", "1.44")}
        subprocess.run(["docker", "compose", "--profile", "optional", "up", "-d", "app"], check=True, env=env)
    console.print("[bold green]Knowledge-base services started.[/bold green]")


@app.command("ingest")
def kb_ingest(
    raw: str = typer.Option("data/raw", "--raw", help="Raw corpus directory."),
    model: str | None = typer.Option(None, "--model", help="LLM model for extraction."),
    build_extraction_instructions: bool = typer.Option(True, "--build-extraction-instructions/--no-extraction-instructions"),
    start_databases: bool = typer.Option(True, "--start-databases/--no-start-databases"),
) -> None:
    """Ingest raw corpus into knowledge bases without clearing existing data."""
    _start_databases_if_needed(start_databases)
    summary = reset_load_knowledge_bases(raw_dir=raw, clear=False, model=model, build_extraction_instructions=build_extraction_instructions)
    _print_load_summary(summary)


@app.command("reset-ingest")
def kb_reset_ingest(
    raw: str = typer.Option("data/raw", "--raw", help="Raw corpus directory."),
    model: str | None = typer.Option(None, "--model", help="LLM model for extraction."),
    build_extraction_instructions: bool = typer.Option(True, "--build-extraction-instructions/--no-extraction-instructions"),
    start_databases: bool = typer.Option(True, "--start-databases/--no-start-databases"),
) -> None:
    """Clear knowledge bases and reload them directly from raw corpus."""
    _start_databases_if_needed(start_databases)
    summary = reset_load_knowledge_bases(raw_dir=raw, clear=True, model=model, build_extraction_instructions=build_extraction_instructions)
    _print_load_summary(summary)


def _start_databases_if_needed(enabled: bool) -> None:
    """Start local knowledge-base engines before a load operation."""
    if not enabled:
        return
    console.print("[bold]Starting knowledge-base engines[/bold]")
    env = {**os.environ, "DOCKER_API_VERSION": os.getenv("DOCKER_API_VERSION", "1.44")}
    subprocess.run(["docker", "compose", "--profile", "optional", "up", "-d", "neo4j", "qdrant", "postgres", "redis"], check=True, env=env)


def _print_engine_status() -> None:
    """Print physical database engine status."""
    table = Table(title="Knowledge Base Engines")
    table.add_column("Engine", max_width=9, no_wrap=True, overflow="ellipsis")
    table.add_column("Status", max_width=10, no_wrap=True, overflow="ellipsis")
    table.add_column("Container", max_width=24, no_wrap=True, overflow="ellipsis")
    table.add_column("Database", max_width=18, no_wrap=True, overflow="ellipsis")
    table.add_column("Host endpoint", max_width=24, no_wrap=True, overflow="ellipsis")
    table.add_column("Ports", max_width=14, no_wrap=True, overflow="ellipsis")
    table.add_column("Usage", max_width=56, no_wrap=False, overflow="fold")

    for spec in ENGINE_SPECS:
        container = _first_existing_container(spec["containers"])
        table.add_row(
            str(spec["name"]),
            str(container["status"]) if container else "not_created",
            _compact_cell(str(container["name"]), max_chars=24) if container else "-",
            str(spec["database"]),
            _short_host_endpoint(str(spec["host_endpoint"])),
            _short_ports(str(container["ports"])) if container else "-",
            str(spec["usage"]),
        )
    Console(width=150).print(table)


def _compact_cell(value: str, *, max_chars: int) -> str:
    compact = " ".join(value.split())
    if len(compact) <= max_chars:
        return compact
    return f"{compact[: max_chars - 3]}..."


def _compact_ports(value: str) -> str:
    if value == "-" or not value.strip():
        return "-"
    items = [item.strip() for item in value.split(",") if item.strip()]
    if len(items) <= 3:
        return "\n".join(items)
    visible = "\n".join(items[:3])
    return f"{visible}\n+{len(items) - 3} more"


def _short_host_endpoint(value: str) -> str:
    compact = " ".join(value.split())
    compact = compact.replace("http://localhost:", "localhost:")
    compact = compact.replace("bolt://localhost:", "localhost:")
    compact = compact.replace("postgresql://localhost:", "localhost:")
    compact = compact.replace("redis://localhost:", "localhost:")
    compact = compact.replace("/0", "")
    return _compact_cell(compact.replace(" / ", ", "), max_chars=24)


def _short_ports(value: str) -> str:
    if value == "-" or not value.strip():
        return "-"
    host_ports: list[str] = []
    for item in value.split(","):
        token = item.strip()
        if "->" not in token:
            continue
        left = token.split("->", 1)[0].strip()
        if ":" in left:
            host_port = left.rsplit(":", 1)[-1]
        else:
            host_port = left
        if host_port.isdigit() and host_port not in host_ports:
            host_ports.append(host_port)
    if not host_ports:
        return _compact_cell(value, max_chars=14)
    return ",".join(host_ports)


def _first_existing_container(names: list[str]) -> dict[str, str] | None:
    for name in names:
        inspected = _inspect_container(name)
        if inspected is not None:
            return inspected
    return None


def _inspect_container(name: str) -> dict[str, str] | None:
    try:
        completed = subprocess.run(
            ["docker", "inspect", name],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return {"name": name, "status": "docker_not_available", "ports": "-"}
    if completed.returncode != 0:
        return None
    data = json.loads(completed.stdout)
    if not data:
        return None
    container = data[0]
    state = container.get("State", {})
    status = str(state.get("Status") or "unknown")
    health = state.get("Health", {}).get("Status")
    if health:
        status = f"{status}/{health}"
    return {
        "name": str(container.get("Name", name)).lstrip("/"),
        "status": status,
        "ports": _format_ports(container.get("NetworkSettings", {}).get("Ports", {})),
    }


def _format_ports(ports: dict[str, object]) -> str:
    rendered = []
    for container_port, bindings in sorted(ports.items()):
        if not bindings:
            rendered.append(f"{container_port}->unpublished")
            continue
        for binding in bindings:
            if isinstance(binding, dict):
                host_ip = binding.get("HostIp") or "0.0.0.0"
                host_port = binding.get("HostPort") or ""
                rendered.append(f"{host_ip}:{host_port}->{container_port}")
    return ", ".join(rendered) if rendered else "-"


def _print_load_summary(summary: dict[str, object]) -> None:
    """Print a compact table for a load or reset-load operation."""
    table = Table(title="Knowledge Base Load Summary")
    table.add_column("Metric")
    table.add_column("Value")
    for key, value in summary.items():
        table.add_row(str(key), str(value))
    console.print(table)


def main() -> None:
    """Run the platform CLI."""
    app()


if __name__ == "__main__":
    main()
