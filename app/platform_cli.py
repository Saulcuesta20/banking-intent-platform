from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import typer
import yaml
from rich.console import Console
from rich.table import Table

from app.cli import kb as query_knowledge_base
from app.cli import kb_views as show_knowledge_views
from app.factory import (
    build_asset_catalog_store,
    build_asset_set_deployment_service,
    build_enterprise_asset_registry,
    build_ingestion_orchestrator,
    build_knowledge_base_service,
)
from app.config.settings import load_settings
from app.ingestion.orchestrator import IngestionOrchestratorConfig, RoleBasedExtractionInstructionBuilder
from app.ingestion.federated_topology import FederatedKnowledgeTopology
from app.knowledge_base.adapters.document.sqlite import SQLiteDocumentKnowledgeBaseAdapter
from app.knowledge_base.adapters.vector.qdrant import QdrantKnowledgeBaseVectorAdapter

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
    knowledge_base: str | None = typer.Option(None, "--kb", "--knowledge-base", help="Knowledge base/store: catalog, graph, vector, relational, document."),
    owner_kb: str | None = typer.Option(None, "--owner-kb", help="Logical owner KB: process_kb, planning_kb, rules_kb, business_model_kb, qa_kb, document_kb, causality_kb, config_kb."),
    asset_type: str | None = typer.Option(None, "--asset-type", "--asset", help="Asset type, for example flow, process, business_rule, plan, tool."),
    asset_id: str | None = typer.Option(None, "--id", help="Global asset id to inspect."),
    text: str | None = typer.Option(None, "--text", "-q", help="Search text."),
    relation_type: str | None = typer.Option(None, "--relation-type", help="Filter assets that have outbound relationships of this type."),
    store: str = typer.Option("catalog", "--store", help="catalog, document, vector, or all."),
    tree: bool = typer.Option(False, "--tree", help="Include child relationships."),
    metadata: bool = typer.Option(False, "--metadata", help="Show catalog metadata and contract trees."),
    limit: int = typer.Option(50, "--limit", help="Maximum rows."),
    status: str = typer.Option("all", "--status", help="approved, candidate, draft, rejected, deprecated, ready_for_review, in_review, validated, active, retired, or all."),
    output_format: str = typer.Option("table", "--format", help="table, tree, json, or ontology-tree."),
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
        metadata=metadata,
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
    build_extraction_instructions: bool = typer.Option(False, "--build-extraction-instructions/--no-extraction-instructions"),
    catalog_only: bool = typer.Option(False, "--catalog-only/--with-projections", help="Keep only the Unified Catalog updated and skip runtime KB projections."),
    start_databases: bool = typer.Option(True, "--start-databases/--no-start-databases"),
    replay_staged: bool = typer.Option(True, "--replay-staged/--no-replay-staged", help="Replay the richest staged ingestion run into Catalog before re-extracting raw corpus."),
) -> None:
    """Ingest raw corpus into knowledge bases without clearing existing data."""
    _start_databases_if_needed(start_databases)
    summary = _run_canonical_ingestion(
        raw=raw,
        clean=False,
        model=model,
        build_extraction_instructions=build_extraction_instructions,
        catalog_only=catalog_only,
        replay_staged=replay_staged,
    )
    _print_load_summary(summary)


@app.command("reset-ingest")
def kb_reset_ingest(
    raw: str = typer.Option("data/raw", "--raw", help="Raw corpus directory."),
    model: str | None = typer.Option(None, "--model", help="LLM model for extraction."),
    build_extraction_instructions: bool = typer.Option(False, "--build-extraction-instructions/--no-extraction-instructions"),
    reset_all_databases: bool = typer.Option(False, "--all-databases/--catalog-only", help="Reset the Unified Catalog and all KB projections before reloading the corpus."),
    start_databases: bool = typer.Option(False, "--start-databases/--no-start-databases"),
    replay_staged: bool = typer.Option(True, "--replay-staged/--no-replay-staged", help="Replay the richest staged ingestion run into Catalog before re-extracting raw corpus."),
) -> None:
    """Clear knowledge bases and reload them directly from raw corpus."""
    _start_databases_if_needed(start_databases)
    if reset_all_databases:
        _clear_all_knowledge_bases()
    else:
        _clear_runtime_projections()
    summary = _run_canonical_ingestion(
        raw=raw,
        clean=True,
        model=model,
        build_extraction_instructions=build_extraction_instructions,
        catalog_only=not reset_all_databases,
        replay_staged=replay_staged,
    )
    _print_load_summary(summary)


def _run_canonical_ingestion(
    *,
    raw: str,
    clean: bool,
    model: str | None,
    build_extraction_instructions: bool,
    catalog_only: bool,
    replay_staged: bool,
) -> dict[str, object]:
    """Run the same canonical ingestion orchestrator used by API and app CLI."""
    if model:
        os.environ["INTENT_LLM_MODEL"] = model
    settings = load_settings()
    if replay_staged and catalog_only:
        replayed = _replay_best_staged_run(settings.project_root / "app" / "assets" / "staging" / "ingest-runs", clean=clean)
        if replayed is not None:
            return replayed
    ingestion = build_ingestion_orchestrator()
    if build_extraction_instructions:
        ingestion.loader.instruction_builder = RoleBasedExtractionInstructionBuilder()
    result = ingestion.run(
        IngestionOrchestratorConfig(
            raw_path=Path(raw),
            audit_directory=settings.processed_directory / "ingestion_audit",
            knowledge_base_service=None if catalog_only else build_knowledge_base_service(),
            asset_catalog_store=build_asset_catalog_store(),
            asset_registry=build_enterprise_asset_registry(),
            clean=clean,
            apply=True,
            project_knowledge_bases=not catalog_only,
            extraction_instruction_mode="role_based" if build_extraction_instructions else "none",
        )
    )
    return {
        "status": result.mode,
        "source_files": len(result.source_files),
        "flows_persisted": result.flows_persisted,
        "user_tasks_extracted": result.user_tasks_extracted,
        "tools_extracted": result.tools_extracted,
        "canonical_assets_generated": result.canonical_assets_generated,
        "catalog_assets_persisted": result.catalog_assets_persisted,
        "audit_path": str(result.audit_path),
    }


def _replay_best_staged_run(staging_root: Path, *, clean: bool) -> dict[str, object] | None:
    if not staging_root.exists():
        return None
    candidates = []
    for run_dir in staging_root.iterdir():
        if not run_dir.is_dir():
            continue
        manifests = sorted(run_dir.glob("*/asset-set.yaml"))
        if manifests:
            candidates.append((len(manifests), run_dir.stat().st_mtime, run_dir, manifests))
    if not candidates:
        return None

    last_error: str | None = None
    for _, _, selected_run, manifests in sorted(candidates, key=lambda item: (item[0], item[1]), reverse=True):
        if clean:
            build_asset_catalog_store().initialize(clear=True)

        deployment = build_asset_set_deployment_service()
        loaded = []
        skipped = []
        for manifest in manifests:
            try:
                loaded.append(deployment.load(manifest))
            except Exception as exc:
                skipped.append({"manifest": str(manifest), "error": str(exc)})
        if not loaded:
            last_error = skipped[0]["error"] if skipped else "No staged manifests could be loaded."
            continue

        store = build_asset_catalog_store()
        catalog_assets = store.list_assets(status="all", limit=100_000)
        return {
            "status": "apply",
            "source_files": 0,
            "flows_persisted": 0,
            "user_tasks_extracted": 0,
            "tools_extracted": 0,
            "canonical_assets_generated": len(catalog_assets),
            "catalog_assets_persisted": len(catalog_assets),
            "audit_path": f"replayed:{selected_run}",
            "replayed_staged_run": str(selected_run),
            "replayed_asset_sets": len(loaded),
            "skipped_staged_manifests": skipped,
        }
    if last_error:
        console.print(f"[yellow]Staged replay skipped[/yellow]: {last_error}")
    return None


def _start_databases_if_needed(enabled: bool) -> None:
    """Start local knowledge-base engines before a load operation."""
    if not enabled:
        return
    console.print("[bold]Starting knowledge-base engines[/bold]")
    env = {**os.environ, "DOCKER_API_VERSION": os.getenv("DOCKER_API_VERSION", "1.44")}
    subprocess.run(["docker", "compose", "--profile", "optional", "up", "-d", "neo4j", "qdrant", "postgres", "redis"], check=True, env=env)


def _clear_all_knowledge_bases() -> None:
    """Remove the Unified Catalog and every runtime KB projection so reload starts from zero."""
    settings = load_settings()
    try:
        build_asset_catalog_store().initialize(clear=True)
    except Exception:
        pass
    try:
        build_knowledge_base_service().repository.clear()
    except Exception:
        pass

    try:
        document_adapter = SQLiteDocumentKnowledgeBaseAdapter(settings.processed_directory / "knowledge_base" / "document_kb.sqlite")
        document_adapter.initialize(clear=True)
    except Exception:
        pass

    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password))
        with driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
        driver.close()
    except Exception:
        pass

    try:
        vector_adapter = QdrantKnowledgeBaseVectorAdapter(settings.qdrant_host, settings.qdrant_api_key)
        topology = FederatedKnowledgeTopology.from_yaml(settings.federated_topology_path)
        collections = {
            topology.memory_collections.global_asset_index,
            topology.memory_collections.asset_alias_memory,
            topology.memory_collections.relation_alias_memory,
            topology.memory_collections.evidence_memory,
            "enterprise_assets_active",
        }
        for spec in topology.knowledge_bases.values():
            collections.add(spec.vector_collection)
        for collection in collections:
            vector_adapter.clear_collection(collection)
    except Exception:
        pass


def _clear_runtime_projections() -> None:
    """Backward-compatible helper for catalog-only reloads."""
    settings = load_settings()
    try:
        build_knowledge_base_service().repository.clear()
    except Exception:
        pass

    try:
        document_adapter = SQLiteDocumentKnowledgeBaseAdapter(settings.processed_directory / "knowledge_base" / "document_kb.sqlite")
        document_adapter.initialize(clear=True)
    except Exception:
        pass

    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password))
        with driver.session() as session:
            # Delete ALL nodes EXCEPT dimension nodes (KnowledgeBase, Engine, StructuralLayer)
            session.run(
                "MATCH (n) WHERE NOT n:KnowledgeBase AND NOT n:Engine AND NOT n:StructuralLayer "
                "DETACH DELETE n"
            )
        driver.close()
    except Exception:
        pass

    try:
        vector_adapter = QdrantKnowledgeBaseVectorAdapter(settings.qdrant_host, settings.qdrant_api_key)
        topology = FederatedKnowledgeTopology.from_yaml(settings.federated_topology_path)
        collections = {
            topology.memory_collections.global_asset_index,
            topology.memory_collections.asset_alias_memory,
            topology.memory_collections.relation_alias_memory,
            topology.memory_collections.evidence_memory,
        }
        for spec in topology.knowledge_bases.values():
            collections.add(spec.vector_collection)
        for collection in collections:
            vector_adapter.clear_collection(collection)
    except Exception:
        pass


@app.command("stats")
def kb_stats(
    output_format: str = typer.Option("table", "--format", help="table or json."),
) -> None:
    """Show asset counts per Knowledge Base, Layer (business_model_kb), and Engine."""
    settings = load_settings()
    catalog = build_asset_catalog_store()

    topology_path = Path("config/ingestion/federated_topology.yaml")
    topology = yaml.safe_load(topology_path.read_text(encoding="utf-8")) or {}
    kb_defs = topology.get("knowledge_bases") or {}

    projection_rules_path = Path(getattr(settings, "projection_rules_path", Path("config/ingestion/projection_rules.yaml")))
    graph_projection_rules = {}
    if projection_rules_path.exists():
        projection_rules = yaml.safe_load(projection_rules_path.read_text(encoding="utf-8")) or {}
        rules = projection_rules.get("graph_projected_asset_types") or []
        graph_projection_rules = {asset_type: True for asset_type in rules}

    asset_types_path = Path("config/asset_registry/asset_types.yaml")
    asset_types_config = yaml.safe_load(asset_types_path.read_text(encoding="utf-8")) or {}
    at_config = asset_types_config.get("asset_types") or {}

    registry = build_enterprise_asset_registry()

    cat_rows = catalog.list_assets(status="all", limit=10_000)
    cat_counts: dict[str, int] = {}
    for row in cat_rows:
        at = row.get("asset_type") or "unknown"
        cat_counts[at] = cat_counts.get(at, 0) + 1

    # Per-KB, per-asset-type catalog counts
    kb_lookup: dict[str, str] = {}
    for kb_name, kb_def in kb_defs.items():
        for at in kb_def.get("asset_types", []):
            kb_lookup[at] = kb_name

    kb_at_cat: dict[str, dict[str, int]] = {}
    for row in cat_rows:
        at = row.get("asset_type") or "unknown"
        kb_name = kb_lookup.get(at, "unassigned")
        kb_at_cat.setdefault(kb_name, {}).setdefault(at, 0)
        kb_at_cat[kb_name][at] += 1

    # Per-KB, per-layer, per-asset-type counts (for business_model_kb)
    kb_layer_at_cat: dict[str, dict[str, dict[str, int]]] = {}
    for row in cat_rows:
        at = row.get("asset_type") or "unknown"
        kb_name = kb_lookup.get(at, "unassigned")
        if kb_name == "business_model_kb":
            layer = row.get("structural_layer") or row.get("business_layer") or "unclassified"
            if layer == "asset":
                layer = "business_resource"
            kb_layer_at_cat.setdefault(kb_name, {}).setdefault(layer, {}).setdefault(at, 0)
            kb_layer_at_cat[kb_name][layer][at] += 1

    doc_path = settings.processed_directory / "knowledge_base" / "document_kb.sqlite"
    doc_counts: dict[str, int] = {}
    if Path(doc_path).exists():
        import sqlite3
        conn = sqlite3.connect(str(doc_path))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT collection, COUNT(*) as cnt FROM documents GROUP BY collection")
        for r in cur.fetchall():
            doc_counts[r["collection"]] = r["cnt"]
        conn.close()

    graph_counts: dict[str, int] = {}
    graph_kb_asset_counts: dict[str, dict[str, int]] = {}
    graph_kb_layer_counts: dict[str, dict[str, dict[str, int]]] = {}
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password))
        with driver.session() as session:
            # Global graph counts
            result = session.run(
                "MATCH (n:Asset) WHERE n.asset_type IS NOT NULL "
                "RETURN n.asset_type AS at, count(n) AS cnt ORDER BY at"
            )
            for r in result:
                graph_counts[r["at"]] = r["cnt"]

            # Per-KB, per-asset-type graph counts (using OWNED_BY dimension)
            result = session.run(
                "MATCH (a:Asset)-[:OWNED_BY]->(kb:KnowledgeBase) "
                "RETURN kb.name AS kb, a.asset_type AS at, count(a) AS cnt ORDER BY kb, at"
            )
            for r in result:
                graph_kb_asset_counts.setdefault(r["kb"], {}).setdefault(r["at"], r["cnt"])

            # Per-layer counts for business_model_kb (using CLASSIFIES dimension)
            result = session.run(
                "MATCH (a:Asset)-[:OWNED_BY]->(kb:KnowledgeBase {name: 'business_model_kb'}) "
                "OPTIONAL MATCH (sl:StructuralLayer)-[:CLASSIFIES]->(a) "
                "RETURN coalesce(sl.name, 'assets') AS layer, a.asset_type AS at, count(a) AS cnt "
                "ORDER BY layer, at"
            )
            for r in result:
                graph_kb_layer_counts.setdefault("business_model_kb", {}).setdefault(r["layer"], {}).setdefault(r["at"], r["cnt"])

        driver.close()
    except Exception:
        pass

    vector_counts: dict[str, int] = {}
    try:
        from qdrant_client import QdrantClient
        client = QdrantClient(url=settings.qdrant_host, api_key=settings.qdrant_api_key)
        for coll in client.get_collections().collections:
            if "_assets" in coll.name or coll.name.startswith("kb_"):
                for pt in (client.scroll(coll.name, limit=10000, with_payload=True)[0] or []):
                    at = (pt.payload or {}).get("asset_type") or "unknown"
                    vector_counts[at] = vector_counts.get(at, 0) + 1
        client.close()
    except Exception:
        pass

    all_types = sorted(set(list(cat_counts.keys()) + list(doc_counts.keys()) + list(graph_counts.keys()) + list(vector_counts.keys())))
    graph_expected_types = set(graph_projection_rules) if graph_projection_rules else set(all_types)

    # Build rows_by_kb (same as before)
    rows_by_kb: dict[str, list] = {}
    for at in all_types:
        kb_name = kb_lookup.get(at, "unassigned")
        rows_by_kb.setdefault(kb_name, []).append(at)

    # JSON output
    if output_format == "json":
        data = {}
        for kb_name in sorted(rows_by_kb.keys()):
            if kb_name == "business_model_kb":
                data[kb_name] = {}
                for layer_name in sorted(kb_layer_at_cat.get(kb_name, {}).keys()):
                    data[kb_name][layer_name] = []
                    for at in sorted(kb_layer_at_cat[kb_name][layer_name].keys()):
                        c = kb_layer_at_cat[kb_name][layer_name][at]
                        g = graph_counts.get(at, 0)
                        v = vector_counts.get(at, 0)
                        d = doc_counts.get(at, 0)
                        data[kb_name][layer_name].append({
                            "asset_type": at,
                            "catalog": c,
                            "graph": g,
                            "vector": v,
                            "document": d,
                            "total": c + g + v + d,
                        })
            else:
                data[kb_name] = []
                for at in rows_by_kb.get(kb_name, []):
                    c = cat_counts.get(at, 0)
                    g = graph_counts.get(at, 0)
                    v = vector_counts.get(at, 0)
                    d = doc_counts.get(at, 0)
                    data[kb_name].append({
                        "asset_type": at,
                        "catalog": c,
                        "graph": g,
                        "vector": v,
                        "document": d,
                        "total": c + g + v + d,
                    })
        console.print_json(data=data)
        return

    # Engine status header
    engine_status = []
    if graph_counts:
        engine_status.append(f"Neo4j: {sum(graph_counts.values())} nodes")
    else:
        engine_status.append("Neo4j: offline")
    if vector_counts:
        engine_status.append(f"Qdrant: {sum(vector_counts.values())} points")
    else:
        engine_status.append("Qdrant: offline")

    console.print()
    console.print("[bold]Knowledge Base Stats[/bold]")
    console.print(f"  Engines: {', '.join(engine_status)}")
    console.print()

    # Summary
    console.print("[bold cyan]Knowledge Base Summary[/bold cyan]")
    grand_total = 0
    for kb_name in sorted(rows_by_kb.keys()):
        kb_total = sum(cat_counts.get(at, 0) for at in rows_by_kb[kb_name])
        grand_total += kb_total
        console.print(f"  {kb_name:<25} {kb_total:>6} assets")
    console.print()

    # Table header
    hdr = f"{'Asset Type':<20} {'Catalog':>8} {'Graph':>8} {'Vector':>8} {'Document':>8} {'Total':>7}"
    sep = "-" * len(hdr)
    console.print(f"[bold]{sep}[/bold]")
    console.print(f"[bold]{hdr}[/bold]")
    console.print(f"[bold]{sep}[/bold]")

    grand = {"cat": 0, "graph": 0, "vec": 0, "doc": 0}

    for kb_name in sorted(rows_by_kb.keys()):
        kb_sub = {"cat": 0, "graph": 0, "vec": 0, "doc": 0}
        kb_total_assets = sum(cat_counts.get(at, 0) for at in rows_by_kb[kb_name])
        console.print(f"[bold cyan]{kb_name}[/bold cyan] ({kb_total_assets} assets)")

        if kb_name == "business_model_kb":
            # 3-level: layer → asset_type (only for entities)
            # non-entity assets (tool, user_task) shown at KB level without layer
            ontology_path = Path("config/ontology/universal_layers.yaml")
            layer_defs = {}
            if ontology_path.exists():
                ontology_config = yaml.safe_load(ontology_path.read_text(encoding="utf-8")) or {}
                layer_defs = ontology_config.get("layers") or {}

            entity_types = {"entity"}
            layers_in_kb = sorted(
                [l for l in kb_layer_at_cat.get(kb_name, {}).keys() if l != "unclassified"],
                key=lambda l: (list(layer_defs.keys()).index(l) if l in layer_defs else 999, l),
            )

            for layer in layers_in_kb:
                layer_at = kb_layer_at_cat[kb_name][layer]
                # Only entity types go under layer grouping
                entity_in_layer = {at: cnt for at, cnt in layer_at.items() if at in entity_types}
                if not entity_in_layer:
                    continue
                layer_total = sum(entity_in_layer.values())
                console.print(f"  [bold]{layer}[/bold] ({layer_total} assets)")
                for at in sorted(entity_in_layer.keys()):
                    c = entity_in_layer[at]
                    g = graph_kb_layer_counts.get(kb_name, {}).get(layer, {}).get(at, 0)
                    v = vector_counts.get(at, 0)
                    d = doc_counts.get(at, 0)
                    t = c + g + v + d
                    grand["cat"] += c
                    grand["graph"] += g
                    grand["vec"] += v
                    grand["doc"] += d
                    kb_sub["cat"] += c
                    kb_sub["graph"] += g
                    kb_sub["vec"] += v
                    kb_sub["doc"] += d
                    graph_display = f"{g:>8}" if at in graph_expected_types else f"{'n/a':>8}"
                    console.print(f"    {at:<18} {c:>8} {graph_display} {v:>8} {d:>8} {t:>7}")

            # Non-entity assets at KB level (tool, user_task, etc.)
            non_entity_at = {}
            for layer_name, layer_at in kb_layer_at_cat.get(kb_name, {}).items():
                for at, cnt in layer_at.items():
                    if at not in entity_types:
                        non_entity_at.setdefault(at, 0)
                        non_entity_at[at] += cnt
            # Also include any assets not in kb_layer_at_cat (fallback)
            for at in rows_by_kb.get(kb_name, []):
                if at not in entity_types and at not in non_entity_at:
                    non_entity_at[at] = cat_counts.get(at, 0)
            if non_entity_at:
                non_entity_total = sum(non_entity_at.values())
                console.print(f"  [bold]assets[/bold] ({non_entity_total} assets)")
                for at in sorted(non_entity_at.keys()):
                    c = non_entity_at[at]
                    g = graph_kb_asset_counts.get(kb_name, {}).get(at, 0)
                    v = vector_counts.get(at, 0)
                    d = doc_counts.get(at, 0)
                    t = c + g + v + d
                    grand["cat"] += c
                    grand["graph"] += g
                    grand["vec"] += v
                    grand["doc"] += d
                    kb_sub["cat"] += c
                    kb_sub["graph"] += g
                    kb_sub["vec"] += v
                    kb_sub["doc"] += d
                    graph_display = f"{g:>8}" if at in graph_expected_types else f"{'n/a':>8}"
                    console.print(f"    {at:<18} {c:>8} {graph_display} {v:>8} {d:>8} {t:>7}")
        else:
            # 2-level: asset_type only
            for at in rows_by_kb[kb_name]:
                c = cat_counts.get(at, 0)
                g = graph_kb_asset_counts.get(kb_name, {}).get(at, 0)
                v = vector_counts.get(at, 0)
                d = doc_counts.get(at, 0)
                t = c + g + v + d
                grand["cat"] += c
                grand["graph"] += g
                grand["vec"] += v
                grand["doc"] += d
                kb_sub["cat"] += c
                kb_sub["graph"] += g
                kb_sub["vec"] += v
                kb_sub["doc"] += d
                graph_display = f"{g:>8}" if at in graph_expected_types else f"{'n/a':>8}"
                console.print(f"  {at:<18} {c:>8} {graph_display} {v:>8} {d:>8} {t:>7}")

        kb_total = sum(kb_sub.values())
        console.print(f"  [dim]{'subtotal':<18} {kb_sub['cat']:>8} {kb_sub['graph']:>8} {kb_sub['vec']:>8} {kb_sub['doc']:>8} {kb_total:>7}[/dim]")
        console.print()

    gt = sum(grand.values())
    console.print(f"[bold]{sep}[/bold]")
    console.print(f"[bold]{'TOTAL':<20} {grand['cat']:>8} {grand['graph']:>8} {grand['vec']:>8} {grand['doc']:>8} {gt:>7}[/bold]")
    console.print(f"[bold]{sep}[/bold]")
    console.print()
    if graph_projection_rules:
        console.print("[dim]n/a = asset type is not projected to the graph store[/dim]")
        console.print()

    # Structural Layer Mapping (for business_model_kb)
    console.print("[bold cyan]Structural Layer Mapping (business_model_kb)[/bold cyan]")
    console.print()

    ontology_path = Path("config/ontology/universal_layers.yaml")
    if ontology_path.exists():
        ontology_config = yaml.safe_load(ontology_path.read_text(encoding="utf-8")) or {}
        layers = ontology_config.get("layers") or ontology_config.get("ontology_layers", {}).get("layers", {})

        entity_by_layer: dict[str, int] = {}
        for row in cat_rows:
            if row.get("asset_type") == "entity":
                layer = row.get("structural_layer") or row.get("business_layer") or "unclassified"
                if layer == "asset":
                    layer = "business_resource"
                entity_by_layer[layer] = entity_by_layer.get(layer, 0) + 1

        ont_hdr = f"{'Layer':<18} {'Description':<45} {'Entities':>9}"
        ont_sep = "-" * len(ont_hdr)
        console.print(f"[bold]{ont_hdr}[/bold]")
        console.print(f"[bold]{ont_sep}[/bold]")

        total_entities = 0
        for layer_name, layer_def in layers.items():
            desc = layer_def.get("description", "")[:42]
            count = entity_by_layer.get(layer_name, 0)
            total_entities += count
            console.print(f"  {layer_name:<16} {desc:<45} {count:>9}")

        unclassified = entity_by_layer.get("unclassified", 0)
        total_entities += unclassified
        console.print(f"  {'unclassified':<16} {'Entities not yet classified':<45} {unclassified:>9}")
        console.print(f"  {'subtotal':<16} {'':<45} {total_entities:>9}")
        console.print()

        console.print("[bold cyan]Legacy Entity Roles Summary[/bold cyan]")
        role_hdr = f"{'Role':<18} {'Description':<50}"
        role_sep = "-" * len(role_hdr)
        console.print(f"[bold]{role_hdr}[/bold]")
        console.print(f"[bold]{role_sep}[/bold]")

        roles = ontology_config.get("entity_roles") or ontology_config.get("ontology_layers", {}).get("entity_role_definitions", {})
        for role_name, role_desc in roles.items():
            console.print(f"  {role_name:<16} {role_desc[:48]}")
        console.print()
    else:
        console.print("[dim]Ontology config not found at config/ontology/universal_layers.yaml[/dim]")
        console.print()


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
