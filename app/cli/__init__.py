from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from textwrap import indent

import click
import typer
import yaml
from rich.console import Console
from rich.table import Table
from rich.tree import Tree as RichTree
from app.factory import (
    build_asset_catalog_store,
    build_asset_search_service,
    build_asset_sync_service,
    build_asset_validation_service,
    build_ask_service,
    build_enterprise_asset_registry,
    build_enterprise_asset_repository,
    build_ingestion_orchestrator,
    build_knowledge_base_service,
    build_orchestrator_asset_registry,
    build_orchestrator_service,
    build_orchestration_executor_service,
)
from app.config.settings import load_settings
from app.config.model import load_asset_contracts
from app.capability.registry import RegistryCapabilityProvider
from app.ingestion.orchestrator import IngestionOrchestratorConfig
from app.knowledge_base.catalog_store import AssetCatalogStore
from app.knowledge_base.adapters.document import SQLiteDocumentKnowledgeBaseAdapter
from app.knowledge_base.adapters.vector import QdrantKnowledgeBaseVectorAdapter
from app.knowledge_base.source_router import KnowledgeSourceRouter
from app.orchestrator.orchestration_executor import OrchestrationExecutionRequest

console = Console()
app = typer.Typer()


@app.command()
def ask(
    question: str,
    trace: bool = typer.Option(True, "--trace/--no-trace", help="Print component resolution steps."),
    debug_trace: bool = typer.Option(False, "--debug-trace", help="Print detailed class/method trace."),
    full_result: bool = typer.Option(False, "--full-result", help="Print the full result payload."),
    interactive: bool = typer.Option(True, "--interactive/--no-interactive", help="Ask for clarification when the intent is ambiguous."),
) -> None:
    """Ask a banking question using the configured answer service."""
    trace_events: list[tuple[str, str]] = []

    def collect_trace(component: str, message: str) -> None:
        trace_events.append((component, message))

    try:
        ask_service = build_ask_service()
        result = ask_service.resolve(question, trace=collect_trace if trace else None)
    except Exception as exc:
        console.print("[bold red]Error[/bold red] No pude completar la pregunta.")
        console.print(_friendly_error(str(exc)))
        raise typer.Exit(1)
    if trace:
        _print_ask_flow_summary(question, trace_events, result)
        if debug_trace:
            _print_ask_flow_trace(question, trace_events, result)
            _print_debug_events(trace_events)
    if interactive and not result.to_dict()["can_resolve"]:
        clarified_question = _prompt_for_clarification(question, result.to_dict())
        if clarified_question:
            trace_events = []
            try:
                result = ask_service.resolve(clarified_question, trace=collect_trace if trace else None)
            except Exception as exc:
                console.print("[bold red]Error[/bold red] No pude completar la aclaracion.")
                console.print(_friendly_error(str(exc)))
                raise typer.Exit(1)
            if trace:
                _print_ask_flow_summary(clarified_question, trace_events, result)
                if debug_trace:
                    _print_ask_flow_trace(clarified_question, trace_events, result)
                    _print_debug_events(trace_events)
    if interactive and result.to_dict()["can_resolve"]:
        _prompt_for_execution_option(result.to_dict())
    if full_result or not trace:
        console.print(result.to_dict())
        return

    if trace:
        payload = result.to_dict()
        if payload["explanation"]:
            console.print(f'[bold]Why[/bold] {payload["explanation"]}')
        return

    payload = result.to_dict()
    summary = Table(show_header=False, box=None, padding=(0, 1))
    summary.add_column("Field", style="bold")
    summary.add_column("Value")
    summary.add_row("Can resolve", str(payload["can_resolve"]))
    summary.add_row("Selected flow", f'{payload["flow_id"]} ({payload["flow_name"]})')
    summary.add_row("Intent", payload["intent"])
    summary.add_row("Confidence", str(payload["confidence"]))
    summary.add_row("Business event", payload["business_event"])
    summary.add_row("Human approval", str(payload["requires_human_approval"]))
    summary.add_row("Trace file", "see debug_trace file above")
    console.print(summary)

    if payload["explanation"]:
        console.print(f'[bold]Why[/bold] {payload["explanation"]}')

    if payload["plan"]:
        console.print("[bold]Plan[/bold]")
        for index, step in enumerate(payload["plan"], start=1):
            console.print(f"  {index}. {step}")

    if payload["tasks"]:
        console.print("[bold]Tasks[/bold]")
        for task in payload["tasks"]:
            console.print(f'  - {task["task"]} ({task["type"]})')

    if payload["related_capabilities"]:
        shown_tools = payload["related_capabilities"][:12]
        hidden_count = len(payload["related_capabilities"]) - len(shown_tools)
        suffix = f" (+{hidden_count} more)" if hidden_count else ""
        console.print("[bold]Tools[/bold] " + ", ".join(shown_tools) + suffix)

    if payload["related_concepts"]:
        console.print("[bold]Concepts[/bold] " + ", ".join(payload["related_concepts"]))


@app.command("ask-suite")
def ask_suite(
    scenario_file: Path = typer.Option(
        Path("e2e/ask_scenarios.yaml"),
        "--scenario-file",
        "-f",
        help="YAML file with ask scenarios.",
    ),
    scenario_id: str | None = typer.Option(None, "--id", help="Run a single scenario id."),
    limit: int | None = typer.Option(None, "--limit", help="Run only the first N selected scenarios."),
    debug_trace: bool = typer.Option(False, "--debug-trace", help="Print raw trace events for each scenario."),
    full_json: bool = typer.Option(False, "--full-json", help="Print the final JSON report."),
    fail_fast: bool = typer.Option(False, "--fail-fast", help="Stop on the first failed expectation."),
) -> None:
    """Run end-to-end ask scenarios and show routing/evidence decisions."""
    try:
        scenarios = _load_ask_scenarios(scenario_file)
    except Exception as exc:
        console.print(f"[bold red]Invalid scenario file[/bold red]: {scenario_file}")
        console.print(str(exc))
        raise typer.Exit(1)
    if scenario_id:
        scenarios = [scenario for scenario in scenarios if scenario.get("id") == scenario_id]
    if limit is not None:
        scenarios = scenarios[:limit]
    if not scenarios:
        console.print("[bold red]No scenarios selected[/bold red]")
        raise typer.Exit(1)

    try:
        ask_service = build_ask_service()
    except Exception as exc:
        console.print("[bold red]Error[/bold red] No pude iniciar AskService.")
        console.print(_friendly_error(str(exc)))
        raise typer.Exit(1)

    console.print("[bold]Ask E2E suite[/bold]")
    console.print(f"scenario_file: {scenario_file}")
    console.print(f"scenarios: {len(scenarios)}")
    console.print("")

    reports = []
    failures = 0
    for index, scenario in enumerate(scenarios, start=1):
        report = _run_ask_scenario(index, scenario, ask_service, debug_trace)
        reports.append(report)
        failures += 0 if report["passed"] else 1
        if fail_fast and not report["passed"]:
            break

    _print_ask_suite_summary(reports)
    report_path = _write_ask_suite_report(scenario_file, reports)
    console.print(f"[bold]report_file[/bold]: {report_path}")
    if full_json:
        console.print_json(data={"scenario_file": str(scenario_file), "report_file": str(report_path), "reports": reports})
    if failures:
        raise typer.Exit(1)


@app.command("kb-views")
def kb_views() -> None:
    """Show configured knowledge stores/views and asset type placement."""
    registry = build_enterprise_asset_registry()
    payload = {
        "stores": {
            name: {
                "role": registry.get_knowledge_base(name).role,
                "description": registry.get_knowledge_base(name).description,
                "asset_types": registry.asset_types_for_store(name),
            }
            for name in registry.list_knowledge_bases()
        },
        "runtime_views": {
            "catalog": "Catalog of approved YAML/JSON assets and generated flow/process assets.",
            "graph": "Neo4j relationship view for flow/process/entity/task/tool retrieval.",
            "vector": "Semantic text view for approved Q&A and source documents.",
            "document": "Document view for long manuals, corpus chunks, and policy pages.",
            "relational": "Runtime state, audit, approvals, and monitoring.",
            "external_api": "Tool/API view for real-time evidence and service calls.",
        },
    }
    console.print_json(data=payload)


@app.command("kb-route")
def kb_route(query: str) -> None:
    """Preview which knowledge sources/views would be consulted for a query."""
    service = build_knowledge_base_service()
    routes = service.source_router.route(
        question=query,
        search_terms=_kb_search_terms(query),
        question_understanding={"routing_hints": _kb_routing_hints(query)},
        asset_search=build_asset_search_service().search(query).model_dump(mode="json"),
    )
    console.print_json(data={"query": query, "routes": [route.model_dump(mode="json") for route in routes]})


@app.command("kb-show")
def kb_show(
    knowledge_base: str,
    query: str | None = typer.Option(None, "--query", "-q", help="Filter assets by text."),
    status: str = typer.Option("all", "--status", help="approved, draft, candidate, deprecated, rejected, ready_for_review, in_review, validated, active, draft, retired, or all."),
    store: list[str] | None = typer.Option(None, "--store", help="Show only one configured engine/store. Can be repeated."),
    limit: int = typer.Option(50, "--limit", help="Maximum assets to return."),
    full: bool = typer.Option(False, "--full", help="Print full asset payloads."),
) -> None:
    """Show one logical knowledge base by asset type and its configured engines."""
    registry = build_enterprise_asset_registry()
    repository = build_enterprise_asset_repository()
    asset_type = _normalize_kb_asset_type(knowledge_base, registry.list_asset_types())
    config = registry.get_asset_type(asset_type)
    valid_statuses = {"approved", "draft", "candidate", "deprecated", "rejected", "all"}
    if status not in valid_statuses:
        raise typer.BadParameter(f"--status must be one of: {', '.join(sorted(valid_statuses))}")
    configured_stores = registry.stores_for(asset_type)
    selected_stores = store or configured_stores
    unknown_stores = sorted(set(selected_stores) - set(registry.list_knowledge_bases()))
    if unknown_stores:
        raise typer.BadParameter(f"Unknown knowledge store(s): {', '.join(unknown_stores)}")
    unsupported_stores = sorted(set(selected_stores) - set(configured_stores))
    if unsupported_stores:
        raise typer.BadParameter(
            f"{asset_type} is not configured for store(s): {', '.join(unsupported_stores)}"
        )

    assets = repository.list_assets(asset_type=asset_type, approved_only=False)
    if status != "all":
        assets = [asset for asset in assets if asset.status == status]
    if query:
        assets = [asset for asset in assets if _asset_matches_query(asset, query)]
    assets = assets[:limit]
    asset_payloads = (
        [_asset_full_payload(asset) for asset in assets]
        if full
        else [_asset_summary(asset) for asset in assets]
    )
    if asset_type == "tool" and len(asset_payloads) < limit:
        asset_payloads.extend(
            _tool_registry_payloads(
                query=query,
                status=status,
                limit=limit - len(asset_payloads),
                full=full,
                existing_asset_ids={
                    asset.asset_id.removeprefix("tool.")
                    for asset in assets
                },
            )
        )

    payload = {
        "knowledge_base": {
            "name": f"KB-{_plural_asset_type(asset_type)}",
            "asset_type": asset_type,
            "description": config.description,
            "data_owner": "catalog",
            "canonical_data_format": "yaml",
            "configured_stores": configured_stores,
            "route_kind": config.route_kind,
            "direct_route": config.direct_route,
            "executable": config.executable,
            "execution_target": config.execution_target,
            "runtime_usage": config.runtime_usage,
            "valid_relations": config.valid_relations,
        },
        "engines": [
            _knowledge_engine_summary(store_name, registry.get_knowledge_base(store_name))
            for store_name in selected_stores
        ],
        "filters": {
            "query": query,
            "status": status,
            "limit": limit,
        },
        "assets": asset_payloads,
        "count": len(asset_payloads),
    }
    console.print_json(data=payload)


@app.command("kb")
def kb(
    knowledge_base: str | None = typer.Option(None, "--kb", "--knowledge-base", help="Knowledge base/store filter: catalog, graph, vector, relational, document."),
    owner_kb: str | None = typer.Option(None, "--owner-kb", help="Logical owner KB filter, for example process_kb, planning_kb, rules_kb, business_model_kb, qa_kb, document_kb, causality_kb, or config_kb."),
    requested_asset_type: str | None = typer.Option(None, "--asset-type", "--asset", help="Asset type to filter, for example flow, process, business_rule, plan, tool."),
    asset_id: str | None = typer.Option(None, "--id", help="Global asset id to inspect."),
    query: str | None = typer.Option(None, "--text", "--query", "-q", help="Search text."),
    relation_type: str | None = typer.Option(None, "--relation-type", help="Filter assets with an outbound relation of this type."),
    store: str = typer.Option("catalog", "--store", help="catalog, document, vector, or all."),
    tree: bool = typer.Option(False, "--tree", help="Include child relationships as a tree."),
    metadata: bool = typer.Option(False, "--metadata", help="Show catalog metadata and contract trees."),
    limit: int = typer.Option(50, "--limit", help="Maximum rows."),
    status: str = typer.Option("approved", "--status", help="approved, draft, candidate, deprecated, rejected, or all."),
    output_format: str = typer.Option("table", "--format", help="table, tree, or json."),
) -> None:
    """Query catalog and knowledge-base engines with one command."""
    if output_format not in {"table", "tree", "json", "ontology-tree"}:
        raise typer.BadParameter("--format must be table, tree, json, or ontology-tree")
    settings = load_settings()
    registry = build_enterprise_asset_registry()
    catalog = AssetCatalogStore(settings.processed_directory / "knowledge_base" / "asset_catalog.sqlite")
    if not catalog.path.exists():
        console.print("[bold red]Knowledge catalog is not loaded.[/bold red]")
        console.print("Run: kb reset-ingest --raw data/raw/enterprise_dump_2026")
        raise typer.Exit(1)

    if metadata:
        assets = catalog.list_assets(status="all", limit=max(limit, 100))
        asset_index = {str(asset.get("asset_id") or ""): asset for asset in assets if isinstance(asset, dict) and asset.get("asset_id")}
        asset_relations = {asset_id: catalog.children(asset_id) for asset_id in asset_index}
        payload = {
            "filters": {
                "metadata": True,
                "store": store,
                "limit": limit,
                "status": status,
            },
            "catalog_totals": catalog.totals(),
            "metadata": _catalog_metadata_snapshot(catalog),
            "asset_contracts": load_asset_contracts(),
            "assets": assets,
            "asset_index": asset_index,
            "asset_relations": asset_relations,
        }
        if output_format == "json":
            console.print_json(data=payload)
            return
        if output_format == "table":
            _print_kb_metadata_result(payload)
            return
        _print_kb_metadata_tree_result(payload)
        return

    asset_filter = requested_asset_type
    asset_type = _normalize_kb_asset_type(asset_filter, registry.list_asset_types()) if asset_filter else None
    kb_filter = _normalize_knowledge_base_filter(knowledge_base)
    payload: dict[str, object] = {
        "filters": {
            "kb": kb_filter,
            "asset_type": asset_type,
            "asset_id": asset_id,
            "query": query,
            "owner_kb": owner_kb,
            "relation_type": relation_type,
            "store": store,
            "tree": tree,
            "limit": limit,
            "status": status,
        },
        "catalog_totals": catalog.totals(),
    }

    if asset_id:
        asset = catalog.get_asset(asset_id)
        if asset and kb_filter and kb_filter not in [asset.get("primary_kb"), *(asset.get("stores") or [])]:
            asset = None
        if asset and owner_kb and owner_kb != asset.get("primary_kb"):
            asset = None
        payload["asset"] = asset
        if (tree or output_format == "tree") and asset:
            payload["tree"] = _catalog_tree(catalog, asset_id, depth=3)
    else:
        assets = catalog.list_assets(
            asset_type=asset_type,
            knowledge_base=kb_filter,
            owner_kb=owner_kb,
            query=query,
            relation_type=relation_type,
            status=status,
            limit=limit,
        )
        payload["assets"] = assets
        if tree or output_format == "tree":
            payload["trees"] = [
                _catalog_tree(catalog, str(asset["asset_id"]), depth=3)
                for asset in assets
            ]

    if store in {"document", "all"} and query:
        document_kb = SQLiteDocumentKnowledgeBaseAdapter(settings.processed_directory / "knowledge_base" / "document_kb.sqlite")
        payload["document_results"] = document_kb.search_documents(asset_type, query, limit=limit)
    if store in {"vector", "all"} and query:
        vector = QdrantKnowledgeBaseVectorAdapter(_cli_qdrant_host(settings.qdrant_host), settings.qdrant_api_key)
        payload["vector_results"] = vector.search_texts("knowledge_assets", query, limit=limit)

    if output_format == "json":
        console.print_json(data=payload)
        return
    if output_format == "ontology-tree":
        _print_ontology_tree(payload)
        return
    if tree or output_format == "tree":
        _print_kb_query_tree_result(payload)
        return
    _print_kb_query_result(payload)


def _catalog_metadata_snapshot(catalog: AssetCatalogStore) -> dict[str, object]:
    """Return catalog metadata grouped the same way the launcher filters it."""
    assets = catalog.list_assets(status="all", limit=10_000)
    asset_types = sorted({str(asset.get("asset_type") or "") for asset in assets if asset.get("asset_type")})
    knowledge_bases = sorted({store for asset in assets for store in asset.get("stores") or []})
    statuses = sorted({str(asset.get("status") or "") for asset in assets if asset.get("status")})
    tags = sorted({tag for asset in assets for tag in asset.get("tags") or []})
    domains = sorted({str(asset.get("domain_id") or "") for asset in assets if asset.get("domain_id")})
    modules = sorted({str(asset.get("module_id") or "") for asset in assets if asset.get("module_id")})
    return {
        "asset_types": asset_types,
        "knowledge_bases": knowledge_bases,
        "statuses": statuses,
        "tags": tags,
        "domains": domains,
        "modules": modules,
        "counts": {
            "asset_types": dict(Counter(str(asset.get("asset_type") or "") for asset in assets if asset.get("asset_type"))),
            "knowledge_bases": dict(Counter(store for asset in assets for store in asset.get("stores") or [])),
            "statuses": dict(Counter(str(asset.get("status") or "") for asset in assets if asset.get("status"))),
            "tags": dict(Counter(tag for asset in assets for tag in asset.get("tags") or [])),
            "domains": dict(Counter(str(asset.get("domain_id") or "") for asset in assets if asset.get("domain_id"))),
            "modules": dict(Counter(str(asset.get("module_id") or "") for asset in assets if asset.get("module_id"))),
        },
    }


def _print_ontology_tree(payload: dict[str, object]) -> None:
    """Render ontology assets grouped by structural_layer as a rich tree."""
    assets = payload.get("assets")
    if not isinstance(assets, list) or not assets:
        console.print("[bold red]No ontology assets found.[/bold red]")
        return

    filters = payload.get("filters") or {}
    title = filters.get("owner_kb") or filters.get("query") or "ontology"

    root = RichTree(f"[bold]{title}[/bold] ontology_tree")

    by_layer: dict[str, list[dict[str, object]]] = {}
    for asset in assets:
        payload_data = asset.get("payload") if isinstance(asset.get("payload"), dict) else {}
        layer = asset.get("structural_layer") or (payload_data.get("structural_layer") if isinstance(payload_data, dict) else None)
        layer = str(layer or "unclassified")
        by_layer.setdefault(layer, []).append(asset)

    layer_order = [
        "party", "organization", "capability", "portfolio", "offering",
        "program", "channel", "transaction", "agreement", "event",
        "metric", "workforce", "workforce_role", "business_resource", "unclassified",
    ]
    sorted_layers = sorted(by_layer.keys(), key=lambda l: (layer_order.index(l) if l in layer_order else 99, l))

    for layer in sorted_layers:
        layer_assets = by_layer[layer]
        layer_branch = root.add(f"[bold]{layer}[/bold] ({len(layer_assets)} entities)")
        for asset in sorted(layer_assets, key=lambda a: str(a.get("name") or a.get("asset_id") or "")):
            asset_id = asset.get("asset_id") or ""
            name = asset.get("name") or ""
            description = ""
            payload_data = asset.get("payload") if isinstance(asset.get("payload"), dict) else {}
            if isinstance(payload_data, dict):
                description = str(payload_data.get("description") or "")
            aliases = asset.get("aliases") if isinstance(asset.get("aliases"), list) else []
            alias_str = ", ".join(str(a) for a in aliases[:3]) if aliases else ""
            label = f"{name} ({asset_id})"
            if alias_str:
                label += f" [{alias_str}]"
            branch = layer_branch.add(label)
            if description:
                branch.add(_short_text(description, 120))

    Console(width=220).print(root)


def _print_kb_query_result(payload: dict[str, object]) -> None:
    """Render KB query results as database-like tables."""
    filters = payload.get("filters") or {}
    if isinstance(filters, dict):
        query_label = filters.get("query") or filters.get("asset_id") or filters.get("kb") or "all"
        console.print(f"[bold]Knowledge Base Query[/bold] {query_label}")
        console.print(
            f"store={filters.get('store')} status={filters.get('status')} "
            f"asset_type={filters.get('asset_type') or '*'} owner_kb={filters.get('owner_kb') or '*'} "
            f"relation_type={filters.get('relation_type') or '*'} limit={filters.get('limit')}"
        )

    totals = payload.get("catalog_totals")
    if isinstance(totals, dict):
        _print_kb_totals_table(totals)

    asset = payload.get("asset")
    if isinstance(asset, dict):
        _print_kb_assets_table([asset], title="Asset")
    assets = payload.get("assets")
    if isinstance(assets, list):
        _print_kb_assets_table(assets, title="Catalog Assets")

    document_results = payload.get("document_results")
    if isinstance(document_results, list):
        _print_document_results_table(document_results)

    vector_results = payload.get("vector_results")
    if isinstance(vector_results, list):
        _print_vector_results_table(vector_results)

    tree_payload = payload.get("tree")
    if isinstance(tree_payload, dict):
        _print_kb_tree(tree_payload)


def _print_kb_metadata_result(payload: dict[str, object]) -> None:
    """Render catalog metadata and asset contracts in compact tables."""
    filters = payload.get("filters") or {}
    if isinstance(filters, dict):
        console.print("[bold]Catalog Metadata[/bold]")
        console.print(f"store={filters.get('store')} status={filters.get('status')}")
    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        for key in ("asset_types", "knowledge_bases", "statuses", "tags", "domains", "modules"):
            values = metadata.get(key) or []
            if isinstance(values, list):
                console.print(f"{key}: {', '.join(str(value) for value in values) or '-'}")
    contracts = payload.get("asset_contracts")
    if isinstance(contracts, dict):
        _print_asset_contracts_table(contracts)


def _print_kb_metadata_tree_result(payload: dict[str, object]) -> None:
    """Render catalog metadata and asset contracts as a tree."""
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    contracts = payload.get("asset_contracts") if isinstance(payload.get("asset_contracts"), dict) else {}
    assets = payload.get("assets") if isinstance(payload.get("assets"), list) else []
    asset_index = payload.get("asset_index") if isinstance(payload.get("asset_index"), dict) else {}
    asset_relations = payload.get("asset_relations") if isinstance(payload.get("asset_relations"), dict) else {}

    root = RichTree("[bold]catalog_metadata[/bold]")
    _add_metadata_category_tree(root, "asset_types", metadata.get("asset_types"), metadata.get("counts", {}).get("asset_types"))
    _add_metadata_category_tree(
        root,
        "knowledge_bases",
        metadata.get("knowledge_bases"),
        metadata.get("counts", {}).get("knowledge_bases"),
    )
    _add_metadata_category_tree(root, "statuses", metadata.get("statuses"), metadata.get("counts", {}).get("statuses"))
    _add_metadata_category_tree(root, "tags", metadata.get("tags"), metadata.get("counts", {}).get("tags"))
    _add_metadata_category_tree(root, "domains", metadata.get("domains"), metadata.get("counts", {}).get("domains"))
    _add_metadata_category_tree(root, "modules", metadata.get("modules"), metadata.get("counts", {}).get("modules"))

    contracts_branch = root.add("[bold]asset_contracts[/bold]")
    for name, config in contracts.items():
        if isinstance(config, dict):
            branch = contracts_branch.add(name)
            if config.get("description"):
                branch.add(f"description: {config['description']}")
            if config.get("required_fields"):
                branch.add(f"required_fields: {', '.join(str(field) for field in config['required_fields'])}")
            if config.get("optional_fields"):
                branch.add(f"optional_fields: {', '.join(str(field) for field in config['optional_fields'])}")
            relations = config.get("relations") or {}
            if isinstance(relations, dict):
                allowed_relations = relations.get("allowed") or []
                if allowed_relations:
                    branch.add(f"allowed_relations: {', '.join(str(value) for value in allowed_relations)}")
            runtime_semantics = config.get("runtime_semantics") or {}
            if isinstance(runtime_semantics, dict):
                semantics = []
                if runtime_semantics.get("selected_by"):
                    semantics.append(f"selected_by={runtime_semantics['selected_by']}")
                if runtime_semantics.get("triggered_by"):
                    semantics.append(f"triggered_by={runtime_semantics['triggered_by']}")
                if runtime_semantics.get("execution_target"):
                    semantics.append(f"execution_target={runtime_semantics['execution_target']}")
                if semantics:
                    branch.add(", ".join(semantics))

    if isinstance(assets, list) and assets:
        assets_branch = root.add("[bold]asset_hierarchy[/bold]")
        by_type: dict[str, list[dict[str, object]]] = {}
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            by_type.setdefault(str(asset.get("asset_type") or "unknown"), []).append(asset)
        for asset_type, typed_assets in sorted(by_type.items()):
            type_branch = assets_branch.add(asset_type)
            for asset in typed_assets:
                _add_catalog_asset_hierarchy(type_branch, asset, asset_index, asset_relations)

    Console(width=220).print(root)


def _print_kb_query_tree_result(payload: dict[str, object]) -> None:
    """Render KB query results as an asset tree."""
    filters = payload.get("filters") if isinstance(payload.get("filters"), dict) else {}
    totals = payload.get("catalog_totals") if isinstance(payload.get("catalog_totals"), dict) else {}
    title = filters.get("query") or filters.get("asset_id") or filters.get("asset_type") or "all"
    root = RichTree(
        "[bold]knowledge_base[/bold] "
        f"name={title} store={filters.get('store')} status={filters.get('status')} "
        f"asset_type={filters.get('asset_type') or '*'}"
    )
    if totals:
        totals_branch = root.add("[bold]asset_totals[/bold]")
        for asset_type, count in totals.items():
            totals_branch.add(f"{asset_type}: {count}")

    tree_payload = payload.get("tree")
    if isinstance(tree_payload, dict):
        _add_catalog_asset_tree(root, tree_payload)

    trees = payload.get("trees")
    if isinstance(trees, list):
        assets_branch = root.add("[bold]assets[/bold]")
        for tree in trees:
            if isinstance(tree, dict):
                _add_catalog_asset_tree(assets_branch, tree)

    if isinstance(payload.get("document_results"), list):
        docs_branch = root.add("[bold]document_results[/bold]")
        for result in payload["document_results"]:
            if isinstance(result, dict):
                docs_branch.add(
                    f"{result.get('document_id')} collection={result.get('collection')} "
                    f"title={result.get('title')}"
                )

    if isinstance(payload.get("vector_results"), list):
        vector_branch = root.add("[bold]vector_results[/bold]")
        for result in payload["vector_results"]:
            if isinstance(result, dict):
                vector_payload = result.get("payload") if isinstance(result.get("payload"), dict) else {}
                vector_branch.add(
                    f"{vector_payload.get('asset_id')} score={result.get('score')} "
                    f"type={vector_payload.get('asset_type')} engine=Qdrant"
                )

    Console(width=220).print(root)


def _print_kb_totals_table(totals: dict[str, object]) -> None:
    """Print asset totals grouped by type."""
    table = Table(title="Catalog Totals")
    table.add_column("Asset Type")
    table.add_column("Count", justify="right")
    for asset_type, count in totals.items():
        table.add_row(str(asset_type), str(count))
    console.print(table)


def _print_kb_assets_table(assets: list[dict[str, object]], *, title: str) -> None:
    """Print catalog asset rows with the most useful database columns."""
    table = Table(title=title)
    table.add_column("asset_id", overflow="fold")
    table.add_column("type")
    table.add_column("name", overflow="fold")
    table.add_column("owner_kb")
    table.add_column("stores", overflow="fold")
    table.add_column("status")
    table.add_column("aliases", overflow="fold")
    table.add_column("description", overflow="fold")
    for asset in assets:
        payload = asset.get("payload") if isinstance(asset.get("payload"), dict) else {}
        description = payload.get("description") if isinstance(payload, dict) else ""
        primary_kb = str(asset.get("primary_kb") or "")
        aliases = asset.get("aliases") if isinstance(asset.get("aliases"), list) else []
        table.add_row(
            str(asset.get("asset_id") or ""),
            str(asset.get("asset_type") or ""),
            str(asset.get("name") or ""),
            primary_kb,
            ", ".join(str(item) for item in asset.get("stores") or []),
            str(asset.get("status") or ""),
            _short_text(", ".join(str(item) for item in aliases), 60),
            _short_text(str(description or ""), 90),
        )
    console.print(table)


def _print_document_results_table(results: list[dict[str, object]]) -> None:
    """Print document KB search hits."""
    table = Table(title="Document KB Results")
    table.add_column("collection")
    table.add_column("document_id", overflow="fold")
    table.add_column("title", overflow="fold")
    table.add_column("snippet", overflow="fold")
    for result in results:
        payload = result.get("payload") if isinstance(result.get("payload"), dict) else {}
        text = payload.get("text") or payload.get("document_text") or payload.get("description") or ""
        table.add_row(
            str(result.get("collection") or ""),
            str(result.get("document_id") or ""),
            str(result.get("title") or ""),
            _short_text(str(text), 140),
        )
    console.print(table)


def _print_vector_results_table(results: list[dict[str, object]]) -> None:
    """Print vector KB search hits."""
    table = Table(title="Vector KB Results")
    table.add_column("score", justify="right")
    table.add_column("asset_id", overflow="fold")
    table.add_column("type")
    table.add_column("name", overflow="fold")
    table.add_column("snippet", overflow="fold")
    for result in results:
        payload = result.get("payload") if isinstance(result.get("payload"), dict) else {}
        score = result.get("score")
        table.add_row(
            f"{float(score):.4f}" if isinstance(score, int | float) else str(score or ""),
            str(payload.get("asset_id") or ""),
            str(payload.get("asset_type") or ""),
            str(payload.get("name") or ""),
            _short_text(str(payload.get("text") or ""), 140),
        )
    console.print(table)


def _print_kb_tree(tree_payload: dict[str, object]) -> None:
    """Print asset relationships as an indented tree."""
    root = RichTree(_asset_tree_label(tree_payload.get("asset") or {"asset_id": tree_payload.get("asset_id")}))
    for child in tree_payload.get("children") or []:
        if isinstance(child, dict):
            _add_kb_tree_node(root, child)
    Console(width=220).print(root)


def _add_catalog_asset_tree(parent: RichTree, tree_payload: dict[str, object]) -> None:
    """Attach a full asset tree to a parent tree."""
    asset = tree_payload.get("asset") if isinstance(tree_payload.get("asset"), dict) else None
    branch = parent.add(_asset_tree_label(asset or {"asset_id": tree_payload.get("asset_id")}))
    for child in tree_payload.get("children") or []:
        if isinstance(child, dict):
            _add_kb_tree_node(branch, child)


def _add_kb_tree_node(parent: RichTree, node: dict[str, object]) -> None:
    """Attach one relationship node and its children to a Rich tree."""
    target = node.get("target") if isinstance(node.get("target"), dict) else {}
    relation = node.get("relation_type")
    reference = " reference=true" if node.get("is_reference") else ""
    label = f"{relation} -> {_asset_tree_label(target or {'asset_id': node.get('target_asset_id')})}{reference}"
    branch = parent.add(label)
    for child in node.get("children") or []:
        if isinstance(child, dict):
            _add_kb_tree_node(branch, child)


def _add_metadata_category_tree(
    parent: RichTree,
    category: str,
    values: list[object] | dict[str, object] | None,
    counts: dict[str, object] | None,
) -> None:
    """Attach one catalog metadata category to a Rich tree."""
    branch = parent.add(f"[bold]{category}[/bold]")
    if isinstance(values, list):
        for value in values:
            label = str(value)
            count = counts.get(label) if isinstance(counts, dict) else None
            branch.add(f"{label}{f' ({count})' if count is not None else ''}")


def _add_catalog_asset_hierarchy(
    parent: RichTree,
    asset: dict[str, object],
    asset_index: dict[str, object],
    asset_relations: dict[str, object],
) -> None:
    """Render one asset with payload-driven hierarchy and linked catalog relations."""
    branch = parent.add(_asset_tree_label(asset))
    asset_payload = asset.get("payload") if isinstance(asset.get("payload"), dict) else {}
    if not isinstance(asset_payload, dict):
        asset_payload = {}

    if asset.get("asset_type") == "flow":
        _add_flow_payload_branch(branch, asset_payload)
    elif asset.get("asset_type") == "user_task":
        _add_user_task_payload_branch(branch, asset_payload)

    asset_id = str(asset.get("asset_id") or "")
    if asset_id:
        relation_rows = asset_relations.get(asset_id) if isinstance(asset_relations, dict) else None
        if relation_rows:
            relations_branch = branch.add("catalog_relations")
            for relation in relation_rows:
                if not isinstance(relation, dict):
                    continue
                target = relation.get("target") if isinstance(relation.get("target"), dict) else {}
                relation_branch = relations_branch.add(
                    f"{relation.get('relation_type')} -> {_asset_tree_label(target or {'asset_id': relation.get('target_asset_id')})}"
                )
                if target and target.get("asset_type") in {"flow", "user_task"}:
                    relation_asset = asset_index.get(str(target.get("asset_id") or ""))
                    if isinstance(relation_asset, dict):
                        relation_payload = relation_asset.get("payload") if isinstance(relation_asset.get("payload"), dict) else {}
                        if relation_payload:
                            if relation_asset.get("asset_type") == "flow":
                                _add_flow_payload_branch(relation_branch, relation_payload)
                            elif relation_asset.get("asset_type") == "user_task":
                                _add_user_task_payload_branch(relation_branch, relation_payload)


def _add_flow_payload_branch(parent: RichTree, payload: dict[str, object]) -> None:
    """Render flow payload as a nested task/action/tool tree."""
    user_tasks = payload.get("user_tasks")
    if not isinstance(user_tasks, list) or not user_tasks:
        return
    tasks_branch = parent.add("user_tasks")
    for user_task in user_tasks:
        if not isinstance(user_task, dict):
            continue
        task_branch = tasks_branch.add(
            f"{user_task.get('user_task_id') or user_task.get('task') or 'task'} | "
            f"{user_task.get('name') or user_task.get('task') or ''}"
        )
        _add_user_task_payload_branch(task_branch, user_task)


def _add_user_task_payload_branch(parent: RichTree, payload: dict[str, object]) -> None:
    """Render one user task with its actions and tools."""
    user_actions = payload.get("user_actions")
    if isinstance(user_actions, list) and user_actions:
        actions_branch = parent.add("user_actions")
        for action in user_actions:
            if not isinstance(action, dict):
                continue
            action_label = (
                f"{action.get('action_id') or action.get('action')} | "
                f"type={action.get('type')} impl={action.get('implementation_type')} "
                f"state={action.get('lifecycle_state') or 'not_started'}"
            )
            action_branch = actions_branch.add(action_label)
            tool_ids = action.get("tool_ids") if isinstance(action.get("tool_ids"), list) else []
            if tool_ids:
                tools_branch = action_branch.add("tools")
                for tool_id in tool_ids:
                    tools_branch.add(str(tool_id))

    tools = payload.get("tools")
    if isinstance(tools, list) and tools:
        tools_branch = parent.add("tools")
        for tool in tools:
            if not isinstance(tool, dict):
                continue
            tools_branch.add(
                f"{tool.get('tool_id') or ''} | {tool.get('tool_type') or ''} | {tool.get('operation') or ''}"
            )


def _print_asset_contracts_table(contracts: dict[str, dict[str, object]]) -> None:
    """Print asset contracts as a compact summary table."""
    table = Table(title="Asset Contracts")
    table.add_column("asset_type")
    table.add_column("required_fields", overflow="fold")
    table.add_column("optional_fields", overflow="fold")
    table.add_column("allowed_relations", overflow="fold")
    for name, config in contracts.items():
        if not isinstance(config, dict):
            continue
        relations = config.get("relations") or {}
        allowed_relations = relations.get("allowed") if isinstance(relations, dict) else []
        table.add_row(
            name,
            ", ".join(str(field) for field in config.get("required_fields") or []),
            ", ".join(str(field) for field in config.get("optional_fields") or []),
            ", ".join(str(value) for value in allowed_relations or []),
        )
    console.print(table)


def _asset_tree_label(asset: dict[str, object]) -> str:
    """Return an informative one-line label for an asset tree node."""
    asset_id = asset.get("asset_id") or "unknown"
    asset_type = asset.get("asset_type") or "?"
    status = asset.get("status") or ""
    primary_kb = str(asset.get("primary_kb") or "")
    stores = asset.get("stores") or []
    all_kbs = "+".join(_compact_kb_name(str(item)) for item in stores)
    return (
        f"{asset_id} | typ={asset_type} | "
        f"kb={_compact_kb_name(primary_kb) or '?'} | "
        f"sts={status or '?'} | kbs={all_kbs or '-'}"
    )


def _short_text(value: str, max_length: int) -> str:
    """Trim long table cells without hiding the important beginning."""
    compact = " ".join(value.split())
    if len(compact) <= max_length:
        return compact
    return f"{compact[: max_length - 3]}..."


def _knowledge_engine_name(store: str) -> str:
    """Map logical knowledge-base stores to their backing database engine."""
    return {
        "graph": "Neo4j",
        "vector": "Qdrant",
        "document": "SQLite Document KB",
        "repository": "Catalog/Repository",
        "relational": "Postgres/RDBMS",
    }.get(store, store or "")


def _compact_kb_name(store: str) -> str:
    """Shorten common KB names so tree rows stay on one line."""
    return {
        "repository": "repo",
        "relational": "rdbms",
        "document": "doc",
    }.get(store, store)


def _normalize_knowledge_base_filter(value: str | None) -> str | None:
    """Normalize user-facing KB names to logical catalog store names."""
    if not value:
        return None
    normalized = value.strip().lower().replace("-", "_")
    aliases = {
        "repo": "repository",
        "catalog": "repository",
        "graphdb": "graph",
        "neo4j": "graph",
        "graphrag": "graph",
        "qdrant": "vector",
        "semantic": "vector",
        "rag": "vector",
        "postgres": "relational",
        "postgresql": "relational",
        "rdbms": "relational",
        "sqlite": "document",
        "documents": "document",
        "doc": "document",
    }
    normalized = aliases.get(normalized, normalized)
    allowed = {"repository", "graph", "vector", "relational", "document"}
    if normalized not in allowed:
        raise typer.BadParameter(f"--kb must be one of: {', '.join(sorted(allowed))}")
    return normalized


@app.command("kb-search")
def kb_search(
    query: str,
    view: str = typer.Option("all", "--view", help="catalog, graph, or all."),
    asset_type: list[str] | None = typer.Option(None, "--type", help="Catalog asset type filter. Can be repeated."),
    limit: int = typer.Option(10, "--limit", help="Maximum results per view."),
    full: bool = typer.Option(False, "--full", help="Print full records/assets."),
) -> None:
    """Search knowledge-base views directly without running full ask."""
    if view not in {"repository", "graph", "all"}:
        raise typer.BadParameter("--view must be catalog, graph, or all")
    payload: dict[str, object] = {"query": query, "view": view}
    if view in {"repository", "all"}:
        asset_result = build_asset_search_service().search(query, asset_types=asset_type or None, limit=limit)
        payload["repository"] = (
            asset_result.model_dump(mode="json")
            if full
            else {
                "primary_assets": [_asset_summary(asset) for asset in asset_result.primary_assets],
                "supporting_assets": [_asset_summary(asset) for asset in asset_result.supporting_assets],
                "evidence_assets": [_asset_summary(asset) for asset in asset_result.evidence_assets],
            }
        )
    if view in {"graph", "all"}:
        records = build_knowledge_base_service().search(_kb_search_terms(query))[:limit]
        payload["graph"] = (
            [record.model_dump(mode="json") for record in records]
            if full
            else [_knowledge_record_summary(record) for record in records]
        )
    console.print_json(data=payload)


@app.command("kb-evidence")
def kb_evidence(
    query: str,
    limit: int = typer.Option(10, "--limit", help="Maximum graph records to include."),
) -> None:
    """Build the evidence bundle for a query using current repository and graph views."""
    search_terms = _kb_search_terms(query)
    knowledge_base = build_knowledge_base_service()
    records = knowledge_base.search(search_terms)[:limit]
    asset_search = build_asset_search_service().search(query, limit=limit)
    asset_payload = {
        "enabled": True,
        "query": asset_search.query,
        "primary_assets": [asset.asset_id for asset in asset_search.primary_assets],
        "supporting_assets": [asset.asset_id for asset in asset_search.supporting_assets],
        "evidence_assets": [asset.asset_id for asset in asset_search.evidence_assets],
    }
    bundle = knowledge_base.build_evidence_bundle(
        question=query,
        search_terms=search_terms,
        records=records,
        question_understanding={"routing_hints": _kb_routing_hints(query), "search_terms": search_terms},
        asset_search=asset_payload,
    )
    console.print_json(
        data={
            "query": query,
            "search_terms": search_terms,
            "candidate_flows": [record.flow_id for record in records],
            "asset_search": asset_payload,
            "evidence_bundle": bundle.to_trace_payload(),
        }
    )


@app.command("kb-query")
def kb_query(
    query: str,
    limit: int = typer.Option(10, "--limit", help="Maximum results per knowledge view."),
    full: bool = typer.Option(False, "--full", help="Print full records/assets."),
) -> None:
    """Query the logical knowledge-base engine across configured knowledge views."""
    search_terms = _kb_search_terms(query)
    asset_result = build_asset_search_service().search(query, limit=limit)
    asset_payload = {
        "enabled": True,
        "query": asset_result.query,
        "primary_assets": [asset.asset_id for asset in asset_result.primary_assets],
        "supporting_assets": [asset.asset_id for asset in asset_result.supporting_assets],
        "evidence_assets": [asset.asset_id for asset in asset_result.evidence_assets],
    }
    routes = KnowledgeSourceRouter().route(
        question=query,
        search_terms=search_terms,
        question_understanding={"routing_hints": _kb_routing_hints(query), "search_terms": search_terms},
        asset_search=asset_payload,
    )

    graph_payload: dict[str, object]
    evidence_payload: dict[str, object]
    try:
        knowledge_base = build_knowledge_base_service()
        records = knowledge_base.search(search_terms)[:limit]
        evidence_bundle = knowledge_base.build_evidence_bundle(
            question=query,
            search_terms=search_terms,
            records=records,
            question_understanding={"routing_hints": _kb_routing_hints(query), "search_terms": search_terms},
            asset_search=asset_payload,
        )
        graph_payload = {
            "status": "ok",
            "records": (
                [record.model_dump(mode="json") for record in records]
                if full
                else [_knowledge_record_summary(record) for record in records]
            ),
        }
        evidence_payload = evidence_bundle.to_trace_payload()
    except Exception as exc:
        graph_payload = {
            "status": "unavailable",
            "reason": _friendly_error(str(exc)),
            "records": [],
        }
        evidence_payload = {
            "routes": [route.model_dump(mode="json") for route in routes],
            "evidence": [],
        }

    repository_payload = (
        asset_result.model_dump(mode="json")
        if full
        else {
            "status": "ok",
            "primary_assets": [_asset_summary(asset) for asset in asset_result.primary_assets],
            "supporting_assets": [_asset_summary(asset) for asset in asset_result.supporting_assets],
            "evidence_assets": [_asset_summary(asset) for asset in asset_result.evidence_assets],
        }
    )
    vector_payload: dict[str, object]
    if asset_result.vector_results:
        vector_payload = {
            "status": "ok",
            "results": (
                asset_result.vector_results
                if full
                else [
                    {"score": item.get("score", 0), "asset_id": item.get("payload", {}).get("asset_id"), "text": str(item.get("payload", {}).get("text", ""))[:200]}
                    for item in asset_result.vector_results
                ]
            ),
        }
    else:
        vector_payload = {
            "status": "no_results",
            "reason": "No vector results returned for this query.",
        }
    console.print_json(
        data={
            "query": query,
            "search_terms": search_terms,
            "knowledge_base_engine": {
                "routes": [route.model_dump(mode="json") for route in routes],
                "views": {
                    "repository": repository_payload,
                    "graph": graph_payload,
                    "vector": vector_payload,
                    "relational": {
                        "status": "runtime_only",
                        "reason": "Postgres adapter exists for runtime/audit state, not ask-time knowledge retrieval yet.",
                    },
                },
                "evidence_bundle": evidence_payload,
            },
        }
    )


def _load_ask_scenarios(scenario_file: Path) -> list[dict]:
    if not scenario_file.exists():
        raise FileNotFoundError(f"Scenario file does not exist: {scenario_file}")
    payload = yaml.safe_load(scenario_file.read_text(encoding="utf-8")) or {}
    scenarios = payload.get("scenarios")
    if not isinstance(scenarios, list):
        raise ValueError("Scenario file must contain a 'scenarios' list.")
    for scenario in scenarios:
        if not isinstance(scenario, dict) or not scenario.get("id") or not scenario.get("question"):
            raise ValueError("Each scenario must define 'id' and 'question'.")
    return scenarios


def _run_ask_scenario(index: int, scenario: dict, ask_service, debug_trace: bool) -> dict:
    scenario_id = scenario["id"]
    question = scenario["question"]
    scenario_type = scenario.get("type") or "unknown"
    expected = scenario.get("expected") or {}
    trace_events: list[tuple[str, str]] = []

    def collect_trace(component: str, message: str) -> None:
        trace_events.append((component, message))

    console.print(f"[bold]Scenario {index}: {scenario_id}[/bold] ({scenario_type})")
    console.print(f"[bold]Question[/bold] {question}")
    try:
        result = ask_service.resolve(question, trace=collect_trace)
        payload = result.to_dict()
        planning = _json_message_value(trace_events, "planning", "output=") or {}
        evidence_bundle = _json_message_value(trace_events, "evidence_bundle", "summary=") or {"routes": [], "evidence": []}
        asset_search = _json_message_value(trace_events, "asset_search", "output=") or {}
        question_understanding = _json_message_value(trace_events, "question_understanding", "output=") or {}
        checks = _evaluate_ask_scenario(expected, payload, planning, evidence_bundle)
        passed = all(check["passed"] for check in checks)
        report = {
            "id": scenario_id,
            "type": scenario_type,
            "question": question,
            "expected": expected,
            "passed": passed,
            "checks": checks,
            "result": payload,
            "planning": planning,
            "knowledge_sources": [route.get("source") for route in evidence_bundle.get("routes", [])],
            "evidence_bundle": evidence_bundle,
            "asset_search": asset_search,
            "question_understanding": question_understanding,
            "trace_file": _message_value(trace_events, "debug_trace", "file="),
            "trace_events": [{"component": component, "message": message} for component, message in trace_events],
        }
        _print_ask_scenario_report(report)
        if debug_trace:
            _print_debug_events(trace_events)
        return report
    except Exception as exc:
        report = {
            "id": scenario_id,
            "type": scenario_type,
            "question": question,
            "expected": expected,
            "passed": False,
            "checks": [{"name": "runtime", "passed": False, "expected": "scenario completes", "actual": str(exc)}],
            "error": _friendly_error(str(exc)),
            "trace_events": [{"component": component, "message": message} for component, message in trace_events],
        }
        _print_ask_scenario_report(report)
        return report


def _evaluate_ask_scenario(expected: dict, payload: dict, planning: dict, evidence_bundle: dict) -> list[dict]:
    checks = []
    route = payload.get("route") or planning.get("route") or {}
    route_mode = route.get("mode")
    if expected.get("route_mode"):
        checks.append(
            {
                "name": "route_mode",
                "expected": expected["route_mode"],
                "actual": route_mode,
                "passed": route_mode == expected["route_mode"],
            }
        )
    if expected.get("selected_flow_id"):
        checks.append(
            {
                "name": "selected_flow_id",
                "expected": expected["selected_flow_id"],
                "actual": payload.get("flow_id"),
                "passed": payload.get("flow_id") == expected["selected_flow_id"],
            }
        )
    expected_actions = expected.get("resolution_actions") or []
    if expected_actions:
        actual_actions = _resolution_actions(payload, planning)
        checks.append(
            {
                "name": "resolution_actions",
                "expected": expected_actions,
                "actual": actual_actions,
                "passed": all(action in actual_actions for action in expected_actions),
            }
        )
    expected_sources = expected.get("knowledge_sources") or []
    if expected_sources:
        actual_sources = [route.get("source") for route in evidence_bundle.get("routes", [])]
        checks.append(
            {
                "name": "knowledge_sources",
                "expected": expected_sources,
                "actual": actual_sources,
                "passed": all(source in actual_sources for source in expected_sources),
            }
        )
    expected_targets = expected.get("known_targets") or []
    if expected_targets:
        actual_targets = _known_target_ids(payload, planning)
        checks.append(
            {
                "name": "known_targets",
                "expected": expected_targets,
                "actual": actual_targets,
                "passed": all(target in actual_targets for target in expected_targets),
            }
        )
    if not checks:
        checks.append({"name": "runtime", "expected": "scenario completes", "actual": "completed", "passed": True})
    return checks


def _resolution_actions(payload: dict, planning: dict) -> list[str]:
    user_needs = payload.get("user_needs") or planning.get("user_needs") or []
    actions = []
    for need in user_needs:
        action = need.get("resolution_action")
        if action and action not in actions:
            actions.append(action)
    return actions


def _known_target_ids(payload: dict, planning: dict) -> list[str]:
    user_needs = payload.get("user_needs") or planning.get("user_needs") or []
    values = []
    for need in user_needs:
        for target in need.get("known_targets") or []:
            target_type = target.get("type")
            target_id = target.get("id")
            if target_type and target_id:
                values.append(f"{target_type}:{target_id}")
    return values


def _print_ask_scenario_report(report: dict) -> None:
    status = "[green]PASS[/green]" if report["passed"] else "[red]FAIL[/red]"
    console.print(f"[bold]Status[/bold] {status}")
    if report.get("error"):
        console.print(f"[bold red]Error[/bold red] {report['error']}")
        console.print("")
        return
    result = report["result"]
    planning = report.get("planning") or {}
    route = result.get("route") or planning.get("route") or {}
    actions = _resolution_actions(result, planning)
    knowledge_sources = report.get("knowledge_sources") or []
    trace_file = report.get("trace_file") or "not written"
    console.print(f"[bold]route.mode[/bold]: {route.get('mode') or 'unknown'}")
    console.print(f"[bold]resolution_actions[/bold]: {', '.join(actions) or 'none'}")
    console.print(f"[bold]knowledge_sources[/bold]: {', '.join(knowledge_sources) or 'none'}")
    console.print(f"[bold]selected_flow[/bold]: {result.get('flow_id')} ({result.get('flow_name')})")
    console.print(f"[bold]can_resolve[/bold]: {result.get('can_resolve')}")
    console.print(f"[bold]requires_execution_confirmation[/bold]: {result.get('requires_execution_confirmation')}")
    console.print(f"[bold]trace_file[/bold]: {trace_file}")
    failed_checks = [check for check in report["checks"] if not check["passed"]]
    if failed_checks:
        console.print("[bold red]failed_checks[/bold red]:")
        for check in failed_checks:
            console.print(f"  - {check['name']}: expected={check['expected']} actual={check['actual']}")
    else:
        console.print("[bold]checks[/bold]: all passed")
    console.print("")


def _print_ask_suite_summary(reports: list[dict]) -> None:
    table = Table(title="Ask E2E Results")
    table.add_column("Scenario")
    table.add_column("Type")
    table.add_column("Status")
    table.add_column("Route")
    table.add_column("Resolution")
    table.add_column("Sources")
    table.add_column("Flow")
    for report in reports:
        result = report.get("result") or {}
        planning = report.get("planning") or {}
        route = result.get("route") or planning.get("route") or {}
        status = "PASS" if report.get("passed") else "FAIL"
        table.add_row(
            report["id"],
            report.get("type") or "unknown",
            status,
            route.get("mode") or "error",
            ", ".join(_resolution_actions(result, planning)) or "none",
            ", ".join(report.get("knowledge_sources") or []) or "none",
            result.get("flow_id") or "none",
        )
    console.print(table)


def _write_ask_suite_report(scenario_file: Path, reports: list[dict]) -> Path:
    settings = load_settings()
    output_directory = settings.processed_directory / "e2e_runs"
    output_directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc)
    path = output_directory / f"ask_suite_{timestamp.strftime('%Y%m%dT%H%M%S%fZ')}.json"
    payload = {
        "timestamp": timestamp.isoformat(),
        "scenario_file": str(scenario_file),
        "passed": all(report.get("passed") for report in reports),
        "reports": reports,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def _kb_search_terms(query: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-zA-Z0-9_áéíóúñÁÉÍÓÚÑ.]+", query.lower())
        if len(token) > 2
    ][:24]


def _kb_routing_hints(query: str) -> dict[str, bool]:
    normalized = query.lower()
    asks_how = any(token in normalized for token in ["como", "cómo", "explica", "funciona"])
    wants_execution = any(token in normalized for token in ["quiero", "necesito", "hacer", "abrir", "transferir", "ejecutar"])
    mentions_process = any(token in normalized for token in ["proceso", "flujo", "pasos"])
    mentions_tool = any(token in normalized for token in ["tool", "api", "backend", "frontend", "boton", "botón", "calcul"])
    return {
        "needs_answer": asks_how or "?" in query,
        "needs_flow": wants_execution,
        "needs_process": mentions_process,
        "needs_tool_explanation": mentions_tool,
        "needs_clarification": False,
    }


def _normalize_kb_asset_type(value: str, known_asset_types: list[str]) -> str:
    normalized = value.lower().strip()
    normalized = normalized.removeprefix("kb-").removeprefix("kb_")
    aliases = {
        "flows": "flow",
        "processes": "process",
        "qas": "qa",
        "questions": "qa",
        "answers": "qa",
        "rules": "business_rule",
        "business_rules": "business_rule",
        "business-rules": "business_rule",
        "concepts": "concept",
        "entities": "entity",
        "tools": "tool",
        "documents": "document",
        "docs": "document",
        "config": "configuration",
        "configs": "configuration",
        "configurations": "configuration",
        "plans": "plan",
    }
    asset_type = aliases.get(normalized, normalized)
    if asset_type not in known_asset_types:
        valid_values = ", ".join([f"KB-{_plural_asset_type(item)}" for item in known_asset_types])
        raise typer.BadParameter(f"Unknown knowledge base '{value}'. Valid examples: {valid_values}")
    return asset_type


def _plural_asset_type(asset_type: str) -> str:
    plural_names = {
        "flow": "flows",
        "process": "processes",
        "qa": "qa",
        "business_rule": "business-rules",
        "concept": "concepts",
        "entity": "entities",
        "tool": "tools",
        "document": "documents",
        "configuration": "configurations",
        "plan": "plans",
    }
    return plural_names.get(asset_type, f"{asset_type}s")


def _knowledge_engine_summary(store_name: str, store_config) -> dict:
    settings = load_settings()
    engine_details = {
        "repository": {
            "database_type": "asset_catalog",
            "engine_name": "EnterpriseAssetRepository",
            "adapter": "AssetCatalogStore + EnterpriseAssetRepository",
            "location": str(settings.processed_directory / "knowledge_base" / "asset_catalog.sqlite"),
            "query_status": "available",
        },
        "graph": {
            "database_type": "graph",
            "engine_name": "Neo4j",
            "adapter": "Neo4jKnowledgeBaseGraphAdapter",
            "location": settings.neo4j_uri,
            "query_status": "available_when_neo4j_is_running",
        },
        "vector": {
            "database_type": "vector",
            "engine_name": "Qdrant",
            "adapter": "QdrantKnowledgeBaseVectorAdapter",
            "location": settings.qdrant_host,
            "query_status": "adapter_exists_not_indexed_yet",
        },
        "relational": {
            "database_type": "relational",
            "engine_name": "Postgres/RDBMS",
            "adapter": "PostgresKnowledgeBaseRelationalAdapter",
            "location": os.getenv("POSTGRES_DSN", "postgresql://localhost:5432/banking_intent"),
            "query_status": "runtime_audit_store_not_kb_retrieval_yet",
        },
    }
    return {
        "store": store_name,
        "role": store_config.role,
        "description": store_config.description,
        **engine_details.get(
            store_name,
            {
                "database_type": "unknown",
                "engine_name": store_name,
                "adapter": "not_configured",
                "location": None,
                "query_status": "unknown",
            },
        ),
    }


def _cli_qdrant_host(configured_host: str) -> str:
    if "://qdrant:" in configured_host:
        return configured_host.replace("://qdrant:", "://localhost:")
    return configured_host


def _asset_matches_query(asset, query: str) -> bool:
    text = " ".join(
        [
            asset.asset_id,
            asset.asset_type,
            asset.name or "",
            asset.description,
            asset.text,
            " ".join(asset.tags),
            " ".join(asset.source_refs),
        ]
    ).lower()
    return all(token in text for token in _kb_search_terms(query))


def _asset_full_payload(asset) -> dict:
    payload = asset.model_dump(mode="json")
    payload["data_file"] = _asset_data_file(asset)
    payload["data_format"] = _asset_data_format(payload["data_file"])
    return payload


def _asset_data_file(asset) -> str | None:
    data_file = asset.payload.get("_data_file") if isinstance(asset.payload, dict) else None
    if isinstance(data_file, str) and data_file:
        return data_file
    if asset.source_refs:
        return asset.source_refs[0]
    source = asset.payload.get("source") if isinstance(asset.payload, dict) else None
    if isinstance(source, str) and source:
        return source
    source_path = asset.payload.get("metadata", {}).get("source_path") if isinstance(asset.payload, dict) else None
    return source_path if isinstance(source_path, str) and source_path else None


def _asset_data_format(path: str | None) -> str | None:
    if not path:
        return None
    suffix = Path(path).suffix.lower().lstrip(".")
    return suffix or None


def _tool_registry_payloads(
    *,
    query: str | None,
    status: str,
    limit: int,
    full: bool,
    existing_asset_ids: set[str],
) -> list[dict]:
    if status not in {"approved", "all"} or limit <= 0:
        return []
    repository = build_knowledge_base_service().repository
    records = repository.list_all_records() if hasattr(repository, "list_all_records") else []
    tools = [tool.to_dict() for tool in RegistryCapabilityProvider(records).list_registered_tools()]
    results: list[dict] = []
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        tool_id = str(tool.get("tool_id") or "")
        if not tool_id or tool_id in existing_asset_ids:
            continue
        if query and not _tool_registry_matches_query(tool, query):
            continue
        if full:
            results.append(
                {
                    "asset_id": f"tool.{tool_id}",
                    "asset_type": "tool",
                    "status": "approved",
                    "source": "knowledge_base",
                    "payload": tool,
                }
            )
        else:
            results.append(
                {
                    "asset_id": f"tool.{tool_id}",
                    "asset_type": "tool",
                    "name": tool.get("label") or tool_id,
                    "status": "approved",
                    "tool_type": tool.get("tool_type"),
                    "backend_protocol": tool.get("backend_protocol"),
                    "frontend_event": tool.get("frontend_event"),
                    "llm_operation": tool.get("llm_operation"),
                    "source": "knowledge_base",
                    "relations": [
                        {"type": "invoked_by_user_task", "target_asset_id": f"user_task.{user_task}", "metadata": {}}
                        for user_task in tool.get("user_tasks", [])[:4]
                    ],
                }
            )
        if len(results) >= limit:
            break
    return results


def _tool_registry_matches_query(tool: dict, query: str) -> bool:
    text = " ".join(
        str(tool.get(key) or "")
        for key in [
            "tool_id",
            "tool_type",
            "operation",
            "resource",
            "label",
            "description",
            "backend_protocol",
            "frontend_event",
            "llm_operation",
            "llm_model",
            "llm_provider",
        ]
    ).lower()
    text = " ".join([text, " ".join(tool.get("user_tasks", [])), " ".join(tool.get("flows", []))])
    return all(token in text for token in _kb_search_terms(query))


def _catalog_tree(catalog: AssetCatalogStore, asset_id: str, *, depth: int) -> dict:
    asset = catalog.get_asset(asset_id)
    children = catalog.children(asset_id)
    node = {"asset_id": asset_id, "asset": _asset_tree_summary(asset, asset_id), "children": children}
    if depth <= 1:
        return node
    for child in children:
        resolved_target = child.get("target") if isinstance(child.get("target"), dict) else None
        target_id = str((resolved_target or {}).get("asset_id") or child["target_asset_id"])
        target = catalog.get_asset(target_id) or resolved_target
        child["target"] = _asset_tree_summary(target, target_id)
        child["is_reference"] = target is None
        if target:
            child["children"] = _catalog_tree(catalog, target_id, depth=depth - 1)["children"]
        else:
            child["children"] = []
    return node


def _asset_tree_summary(asset: dict | None, asset_id: str) -> dict:
    """Return compact asset metadata for tree rendering."""
    if not asset:
        return {
            "asset_id": asset_id,
            "asset_type": "?",
            "name": "",
            "status": "reference",
            "primary_kb": "",
            "stores": [],
        }
    return {
        "asset_id": asset.get("asset_id"),
        "asset_type": asset.get("asset_type"),
        "name": asset.get("name"),
        "status": asset.get("status"),
        "primary_kb": asset.get("primary_kb"),
        "stores": asset.get("stores") or [],
    }


def _knowledge_record_summary(record) -> dict:
    return {
        "flow_id": record.flow_id,
        "flow_name": record.flow_name,
        "intent": record.intent,
        "confidence": record.confidence,
        "business_event": record.business_event,
        "concepts": record.concepts[:8],
        "capabilities": record.capabilities[:8],
        "user_tasks": [task.task for task in record.user_tasks[:8]],
        "explanation": record.explanation,
        "provider": record.metadata.get("knowledge_provider"),
        "matched_tokens": (record.metadata.get("graph_rows_preview") or [{}])[0].get("matched_tokens", []),
    }
    console.print(f"[bold]goal[/bold]: {goal.get('summary') or 'unknown'}")
    console.print("[bold]user_needs[/bold]:")
    if user_needs:
        for need in user_needs:
            action = need.get("resolution_action") or "unknown"
            text = need.get("text") or ""
            targets = _format_known_targets(need.get("known_targets") or [])
            suffix = f" -> {targets}" if targets else ""
            console.print(f"  - {action}: {text}{suffix}")
            if need.get("reason"):
                console.print(f"    why: {need['reason']}")
    else:
        console.print("  - none")
    console.print(f"[bold]route.mode[/bold]: {route.get('mode') or 'unknown'}")
    console.print(f"[bold]execution_path[/bold]: {selection_policy.get('path') or 'unknown'}")
    console.print(f"[bold]selection_mode[/bold]: {selection_policy.get('selection_mode') or 'unknown'}")
    if asset_search.get("enabled"):
        console.print("[bold]asset_search[/bold]:")
        console.print(f"  primary: {', '.join(asset_search.get('primary_assets') or []) or 'none'}")
        console.print(f"  supporting: {', '.join(asset_search.get('supporting_assets') or []) or 'none'}")
        console.print(f"  evidence: {', '.join(asset_search.get('evidence_assets') or []) or 'none'}")
    console.print(f"[bold]selected_flow[/bold]: {selected_flow}")

    plan_steps = payload.get("plan") or []
    intention_steps = multiple_intentions_plan.get("steps") or []
    if intention_steps and route.get("mode") == "multiple_intentions":
        console.print("[bold]multiple_intentions_plan[/bold]:")
        for step in intention_steps[:8]:
            tools = step.get("tools") or step.get("actions") or []
            tool_text = f" tools={', '.join(tools[:4])}" if tools else ""
            condition = step.get("condition")
            condition_text = f" condition={condition}" if condition else ""
            console.print(f"  - {step.get('step')} ({step.get('type')}){tool_text}{condition_text}")
        if len(intention_steps) > 8:
            console.print(f"  - ... +{len(intention_steps) - 8} more")
    elif plan_steps:
        console.print("[bold]plan[/bold]: " + ", ".join(plan_steps))
    else:
        console.print("[bold]plan[/bold]: none")

    missing = multiple_intentions_plan.get("missing_capabilities") or []
    if missing:
        console.print("[bold]missing_capabilities[/bold]: " + ", ".join(missing))

    console.print("[bold]execution_options[/bold] (no tools executed yet):")
    if execution_options:
        for index, option in enumerate(execution_options, start=1):
            label = option.get("label") or option.get("option_id") or "option"
            target_ids = option.get("target_ids") or []
            target_text = f" -> {', '.join(target_ids[:4])}" if target_ids else ""
            console.print(f"  {index}. {label}{target_text}")
    else:
        console.print("  1. No ejecutar nada todavia")
    if selection_policy.get("requires_user_selection"):
        console.print("[bold]confirmation[/bold]: required before executing tools/processes")
    else:
        console.print("[bold]confirmation[/bold]: not required for direct answer path")

    console.print(f"[bold]trace_file[/bold]: {trace_file}")
    console.print("Use [bold]ask --debug-trace[/bold] for the full JSON trace or inspect [bold]data/processed/ask_trace[/bold] for the latest file.")
    console.print("")


def _format_known_targets(targets: list[dict]) -> str:
    values = []
    for target in targets[:4]:
        target_type = target.get("type")
        target_id = target.get("id")
        if target_type and target_id:
            values.append(f"{target_type}:{target_id}")
    if len(targets) > 4:
        values.append(f"+{len(targets) - 4} more")
    return ", ".join(values)


def _prompt_for_clarification(question: str, payload: dict) -> str | None:
    options = payload.get("clarification_options") or []
    if not options:
        return None
    console.print("[bold]Necesito una aclaracion[/bold]")
    console.print("La pregunta puede ir por varios caminos. Elige una opcion:")
    for index, option in enumerate(options, start=1):
        label = option.get("label") or option.get("value") or "opcion"
        detail = option.get("flow_id") or option.get("intent") or option.get("value")
        suffix = f" ({detail})" if detail and detail != label else ""
        console.print(f"  {index}. {label}{suffix}")
    console.print("  0. Ninguna / cancelar")
    try:
        raw_choice = _read_prompt("Que quieres hacer", "0")
    except (EOFError, KeyboardInterrupt, click.exceptions.Abort):
        console.print("No se recibio aclaracion; dejo el resultado como unknown.")
        return None
    try:
        selected_index = int(str(raw_choice).strip())
    except ValueError:
        console.print("La opcion no es valida; dejo el resultado como unknown.")
        return None
    if selected_index <= 0 or selected_index > len(options):
        return None
    selected = options[selected_index - 1]
    label = selected.get("label") or selected.get("value")
    value = selected.get("flow_id") or selected.get("intent") or selected.get("value") or label
    console.print(f"Seleccionaste: {label}")
    return f"{question}\nAclaracion del usuario: quiere {label} ({value})."


def _prompt_for_execution_option(payload: dict) -> dict | None:
    if not payload.get("requires_execution_confirmation"):
        return None
    options = payload.get("execution_options") or []
    if not options:
        return None
    policy = payload.get("execution_selection_policy") or {}
    selection_mode = policy.get("selection_mode") or "single"
    console.print("[bold]Validacion requerida antes de ejecutar[/bold]")
    if selection_mode == "multiple":
        console.print("Elige una o varias opciones separadas por coma. No se ejecutara ninguna tool en este paso:")
    else:
        console.print("Elige una opcion. No se ejecutara ninguna tool en este paso:")
    for index, option in enumerate(options, start=1):
        label = option.get("label") or option.get("option_id") or "opcion"
        target_ids = option.get("target_ids") or []
        suffix = f" -> {', '.join(target_ids[:4])}" if target_ids else ""
        console.print(f"  {index}. {label}{suffix}")
    default_index = _default_no_execution_index(options)
    try:
        prompt_label = "Opciones" if selection_mode == "multiple" else "Opcion"
        raw_choice = _read_prompt(prompt_label, str(default_index))
    except (EOFError, KeyboardInterrupt, click.exceptions.Abort):
        selected = options[default_index - 1]
        console.print("No se recibio seleccion interactiva; no se ejecuta nada.")
        console.print(f"Seleccion por defecto: {selected.get('label') or selected.get('option_id')}")
        return {"selection_mode": selection_mode, "selected_options": [selected]}
    selected_indexes = _parse_execution_selection(str(raw_choice), len(options), selection_mode)
    if not selected_indexes:
        console.print("La seleccion no es valida; no se ejecuta nada.")
        return None
    selected_options = [options[index - 1] for index in selected_indexes]
    console.print("[bold]selected_execution_path[/bold]:")
    console.print(f"  path: {policy.get('path') or 'unknown'}")
    console.print(f"  selection_mode: {selection_mode}")
    console.print("  selected_options:")
    for option in selected_options:
        label = option.get("label") or option.get("option_id")
        console.print(f"    - {option.get('option_id')}: {label}")
    console.print("Estado: validado para continuar en un paso de ejecucion posterior; no se ejecutaron tools.")
    return {"selection_mode": selection_mode, "selected_options": selected_options}


def _parse_execution_selection(raw_choice: str, option_count: int, selection_mode: str) -> list[int]:
    if selection_mode == "multiple":
        values = []
        for part in raw_choice.split(","):
            part = part.strip()
            if not part:
                continue
            try:
                value = int(part)
            except ValueError:
                return []
            if value <= 0 or value > option_count:
                return []
            if value not in values:
                values.append(value)
        return values
    try:
        value = int(raw_choice.strip())
    except ValueError:
        return []
    if value <= 0 or value > option_count:
        return []
    return [value]


def _default_no_execution_index(options: list[dict]) -> int:
    for index, option in enumerate(options, start=1):
        if option.get("option_id") == "do_not_execute":
            return index
    return len(options)


def _read_prompt(label: str, default: str) -> str:
    if sys.stdin.isatty():
        return typer.prompt(label, default=default)
    console.print(f"{label} [{default}]: ", end="")
    line = sys.stdin.readline()
    value = line.strip()
    if not value:
        console.print(default)
        return default
    console.print(value)
    return value


def _print_ask_flow_trace(question: str, events: list[tuple[str, str]], result) -> None:
    payload = result.to_dict()
    provider = (
        _message_value(events, "knowledge_base", "provider=")
        or "unknown"
    )
    matched_records = (
        _message_value(events, "knowledge_base", "matched_records=")
        or "0"
    )
    candidate_flows = (
        _message_value(events, "knowledge_base", "candidate_flows=")
        or "none"
    )
    question_provider = _question_understanding_provider(events)
    route = _route(events, payload["can_resolve"])
    trace_file = _message_value(events, "debug_trace", "file=") or "not written"
    llm_answer = _message_value(events, "llm", "answer can_resolve=")
    llm_reason = _message_value(events, "llm", "reason=")
    warning = _message_value(events, "knowledge_base", "warning=")
    question_output = _json_message_value(events, "question_understanding", "output=") or {}
    corrected_question = question_output.get("corrected_question") or question
    corrections = question_output.get("corrections") or []
    search_terms = question_output.get("search_terms") or []
    entities = question_output.get("entities") or []
    possible_intents = question_output.get("possible_intents") or []
    ambiguity = question_output.get("ambiguity")
    llm_json = _json_message_value(events, "llm", "answer_json=")
    planning_json = _json_message_value(events, "planning", "output=") or {}

    console.print("[bold]Banking Ask flow[/bold]")
    console.print("Con tu ejemplo:")
    console.print("")
    console.print(question)
    console.print("")
    console.print("el flujo de ejecucion es:")
    console.print("")

    console.print("[bold]1. Entra la pregunta[/bold]")
    console.print("")
    console.print("Comando:")
    console.print(f'ask "{question}"')
    console.print("Entra por:")
    console.print("app.cli.ask()")
    console.print("Luego llama:")
    console.print("app.factory.build_ask_service()")
    console.print("Ahi se arma el servicio principal:")
    console.print("AskService")
    console.print("con knowledge graph, seleccion de flow, answer, approval, audit y trace.")
    console.print("")

    console.print("[bold]2. LangGraph orquesta los pasos[/bold]")
    console.print("")
    console.print("AskService.resolve() intenta correr LangGraph:")
    console.print("AskService._resolve_with_langgraph()")
    console.print("LangGraph arma este workflow:")
    console.print("")
    console.print("understand_question -> search_knowledge -> analyze_goal -> select_intent -> build_answer")
    console.print("                                                                    -> unknown_result")
    console.print("Si el LLM no encuentra un flow unico, termina en unknown_result.")
    console.print("Si el LLM selecciona un flow valido, termina en build_answer.")
    console.print(f"Ruta real de este run: {route}")
    console.print("")

    console.print("[bold]3. Question Understanding entiende la pregunta[/bold]")
    console.print("")
    console.print("Antes de buscar en el grafo, se llama:")
    console.print("QuestionUnderstandingService.understand(question)")
    console.print("Si estas con AI activo:")
    console.print("LLMQuestionUnderstandingProvider.understand()")
    console.print("El LLM deberia recibir algo como:")
    console.print("")
    console.print("Question:")
    console.print(question)
    console.print("Y devolver JSON con esta forma:")
    console.print(_pretty_json({
        "corrected_question": "pregunta corregida por el LLM",
        "corrections": [{"from": "texto original", "to": "texto corregido"}],
        "search_terms": ["terminos", "sinonimos", "conceptos para buscar en grafo"],
        "entities": ["ConceptosDominio"],
        "possible_intents": ["pistas.de.intencion"],
        "ambiguity": {
            "is_ambiguous": False,
            "reason": "por que es clara o ambigua",
            "options": ["opciones si aplica"],
        },
    }))
    console.print("Aqui el LLM no decide el flow final. Solo ayuda a entender, corregir y ampliar la busqueda.")
    if question_provider:
        console.print("Salida real de Question Understanding en este run:")
        console.print(f"provider: {question_provider}")
        console.print(_pretty_json({
            "corrected_question": corrected_question,
            "corrections": corrections,
            "search_terms": search_terms,
            "entities": entities,
            "possible_intents": possible_intents,
            "ambiguity": ambiguity,
        }))
    console.print("")

    console.print("[bold]4. Knowledge Base busca con el adaptador Neo4j[/bold]")
    console.print("")
    console.print("Luego se llama:")
    console.print("KnowledgeBaseService.search(question)")
    console.print("Usa:")
    console.print("Neo4jKnowledgeBaseGraphAdapter.search()")
    console.print("Este usa los terminos generados por el LLM:")
    for term in search_terms:
        console.print(term)
    console.print("y arma una query Cypher contra Neo4j:")
    console.print("")
    console.print("MATCH (f:Flow)")
    console.print("OPTIONAL MATCH (f)-[:EXEMPLIFIES]->(u:Utterance)")
    console.print("OPTIONAL MATCH (f)-[:RELATES_TO]->(c:Concept)")
    console.print("OPTIONAL MATCH (c)-[:HAS_SYNONYM]->(s:Synonym)")
    console.print("...")
    console.print("WHERE size(matched_tokens) > 0")
    console.print("RETURN flow_id, intent, business_event, utterances, concepts, tools...")
    console.print("Neo4j devuelve candidatos.")
    console.print("Resultado real de knowledge search en este run:")
    console.print(f"provider: {provider}")
    if warning:
        console.print(f"warning: {warning}")
    console.print(f"candidate_flows: {candidate_flows}")
    console.print(f"matched_records: {matched_records}")
    console.print("")

    console.print("[bold]5. Goal Routing analiza meta, necesidades y ruta[/bold]")
    console.print("")
    console.print("Luego se llama:")
    console.print("PlanningService.analyze(question, records, registered_tools)")
    console.print("Este paso produce:")
    console.print("- goal: la meta humana")
    console.print("- user_needs: lo que el usuario necesita resolver")
    console.print("- resolution_action: que hara el sistema con cada necesidad")
    console.print("- route: known_route, multiple_intentions, clarification o unsupported")
    console.print("- multiple_intentions_plan: pasos compuestos con tareas y acciones conocidas")
    if planning_json:
        console.print("Salida real de planning en este run:")
        console.print(_pretty_json(planning_json))
    else:
        console.print("No hubo salida de planning en este run.")
    console.print("")

    console.print("[bold]6. LLM clasifica contra esos candidatos[/bold]")
    console.print("")
    console.print("Despues LangGraph pasa al nodo:")
    console.print("select_intent")
    console.print("Que llama:")
    console.print("FlowSelectionService.select()")
    console.print("Y este usa:")
    console.print("LLMFlowSelectionProvider.select_intent()")
    console.print("Aqui LangChain arma un prompt con:")
    console.print("- pregunta original")
    console.print("- pregunta corregida/contexto")
    console.print("- flows candidatos del grafo")
    console.print("- utterances")
    console.print("- concepts")
    console.print("- acciones")
    console.print("- explicacion de cada flow")
    console.print("El LLM debe responder JSON con esta forma:")
    console.print(_pretty_json({
        "can_resolve": True,
        "selected_flow_id": "flow_id o unknown",
        "confidence": 0.0,
        "reason": "explicacion basada en el grafo",
    }))
    if llm_answer:
        console.print("Respuesta real del LLM en este run:")
        console.print(_pretty_json(llm_json) if llm_json else llm_answer)
        if llm_reason:
            console.print(f"Reason: {llm_reason}")
    else:
        console.print("No hubo decision LLM en este run; esto indica error de configuracion.")
    if route == "unknown":
        console.print("En este caso no debe elegir loan.request ni money.transfer automaticamente.")
    console.print("")

    console.print("[bold]7. LangGraph decide la ruta[/bold]")
    console.print("")
    console.print("LangGraph evalua:")
    console.print("selected_record is None")
    console.print("Si es None toma unknown_result; si existe toma build_answer.")
    console.print(f"Ruta real de este run: {route}")
    if route == "unknown":
        console.print("No toma build_answer porque no hay flow unico.")
    else:
        console.print("Toma build_answer porque hay flow unico seleccionado.")
    console.print("")

    console.print("[bold]8. Se arma la respuesta final[/bold]")
    console.print("")
    console.print("Se llama:")
    console.print("AskService._build_unknown_result()" if route == "unknown" else "AskService._build_projected_result()")
    console.print("Resultado:")
    if route == "unknown":
        console.print(_pretty_json({
            "can_resolve": False,
            "intent": "unknown",
            "business_event": "UnknownBusinessQuestionAsked",
            "requires_human_approval": True,
            "plan": ["clarify_customer_request", "approve_business_case"],
            "explanation": "The request is ambiguous. Ask whether the customer wants to request a loan, send/receive a transfer, or another operation.",
        }))
    else:
        console.print(_pretty_json({
            "can_resolve": payload["can_resolve"],
            "intent": payload["intent"],
            "business_event": payload["business_event"],
            "requires_human_approval": payload["requires_human_approval"],
            "plan": payload["plan"],
            "explanation": payload["explanation"],
        }))
    console.print("Resultado real de este run:")
    console.print(_pretty_json({
        "can_resolve": payload["can_resolve"],
        "intent": payload["intent"],
        "business_event": payload["business_event"],
        "requires_human_approval": payload["requires_human_approval"],
        "plan": payload["plan"],
        "explanation": payload["explanation"],
        "goal": payload.get("goal"),
        "route": payload.get("route"),
        "multiple_intentions_plan": payload.get("multiple_intentions_plan"),
    }))
    console.print("")

    console.print("[bold]Resumen del flujo[/bold]")
    console.print("")
    console.print("CLI")
    console.print(" -> build_ask_service")
    console.print(" -> AskService.resolve")
    console.print(" -> LangGraph")
    console.print("    -> search_knowledge")
    console.print("       -> QuestionUnderstandingService")
    if question_provider == "llm_question_understanding":
        console.print("          -> LLM corrige/entiende pregunta")
    else:
        console.print("          -> LLM requerido no ejecuto")
    console.print("       -> Neo4jKnowledgeBaseGraphAdapter")
    console.print("          -> Neo4j busca flows candidatos")
    console.print("    -> analyze_goal")
    console.print("       -> PlanningService")
    console.print("          -> detecta goal, user_needs, route y multiple_intentions_plan")
    console.print("    -> select_intent")
    if llm_answer:
        console.print("       -> LLMFlowSelectionProvider")
        console.print("          -> LLM decide si hay flow unico")
    else:
        console.print("       -> LLMFlowSelectionProvider")
        console.print("          -> LLM requerido no ejecuto")
    if payload["can_resolve"]:
        console.print("    -> build_answer")
        console.print("       -> proyecta plan y tareas")
    else:
        console.print("    -> unknown_result")
        console.print("       -> pide aclaracion")
    console.print(" -> Audit")
    console.print(" -> ask_trace JSON")
    console.print(f"    -> {trace_file}")
    console.print(" -> respuesta al usuario")
    console.print("")


def _print_debug_events(events: list[tuple[str, str]]) -> None:
    console.print("[bold]Raw debug events[/bold]")
    for component, message in events:
        if message.startswith("file="):
            console.print(f"[bold cyan]{component}[/bold cyan] file: {message.removeprefix('file=')}")
            continue
        if "=" in message and message.startswith(
            (
                "input=",
                "output=",
                "filters=",
                "top_candidates=",
                "params=",
                "rows_preview=",
                "answer_json=",
            )
        ):
            key, value = message.split("=", 1)
            console.print(f"[bold cyan]{component}[/bold cyan] {key}:")
            console.print(indent(_format_trace_value(value), "  "))
            continue
        if message.startswith("query=") or message.startswith("prompt_preview="):
            key, value = message.split("=", 1)
            console.print(f"[bold cyan]{component}[/bold cyan] {key}:")
            console.print(indent(value, "  "))
            continue
        console.print(f"[bold cyan]{component}[/bold cyan] {message}")


def _message_value(events: list[tuple[str, str]], component: str, prefix: str) -> str | None:
    for event_component, message in events:
        if event_component == component and message.startswith(prefix):
            return message.removeprefix(prefix)
    return None


def _json_message_value(events: list[tuple[str, str]], component: str, prefix: str):
    value = _message_value(events, component, prefix)
    if value is None:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def _pretty_json(value) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False)


def _question_understanding_provider(events: list[tuple[str, str]]) -> str | None:
    for component, message in events:
        if component == "question_understanding" and message.startswith("provider="):
            return message.split(" ", 1)[0].removeprefix("provider=")
    return None


def _route(events: list[tuple[str, str]], can_resolve: bool) -> str:
    for component, message in events:
        if component == "orchestration" and "method=_ask_route_after_selection output=" in message:
            raw = message.split("output=", 1)[1]
            try:
                return json.loads(raw)["route"]
            except (json.JSONDecodeError, KeyError):
                break
    return "project" if can_resolve else "unknown"


def _format_trace_value(value: str) -> str:
    try:
        return json.dumps(json.loads(value), indent=2, ensure_ascii=False)
    except json.JSONDecodeError:
        return value


def _friendly_error(message: str) -> str:
    if "Cannot resolve address" in message and "neo4j" in message.lower():
        return (
            "Neo4j no esta disponible desde este proceso. Revisa que el contenedor este arriba "
            "y que el comando se ejecute en la misma red Docker."
        )
    if "OPENAI_API_KEY" in message:
        return "Falta configurar la API key. Define OPENAI_API_KEY y USE_AI_PROVIDERS=true."
    if "USE_AI_PROVIDERS must be true" in message:
        return "El flujo ask requiere USE_AI_PROVIDERS=true. Define la variable de entorno y vuelve a ejecutar ask."
    return message


@app.command()
def ingest(source: Path) -> None:
    """Ingest raw corpus into the knowledge base."""
    settings = load_settings()
    ingestion = build_ingestion_orchestrator()
    result = ingestion.run(
        IngestionOrchestratorConfig(
            raw_path=source,
            audit_directory=settings.processed_directory / "ingestion_audit",
            knowledge_base_service=build_knowledge_base_service(),
            asset_catalog_store=build_asset_catalog_store(),
            asset_registry=build_enterprise_asset_registry(),
            apply=True,
        )
    )
    console.print_json(
        data={
            "status": "ok",
            "source": str(source),
            "flows_persisted": result.flows_persisted,
            "canonical_assets_generated": result.canonical_assets_generated,
            "catalog_assets_persisted": result.catalog_assets_persisted,
            "audit_path": str(result.audit_path),
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


@app.command("orchestrator-assets")
def orchestrator_assets() -> None:
    """List registered flow and process assets known by the orchestrator."""
    registry = build_orchestrator_asset_registry()
    console.print_json(data=registry.list_assets())


@app.command("orchestrator-instances")
def orchestrator_instances(
    active_only: bool = typer.Option(True, "--active-only/--all", help="Show active instances or every known instance."),
) -> None:
    """List orchestrator instances from the active instance registry."""
    orchestrator = build_orchestrator_service()
    instances = orchestrator.list_active_instances() if active_only else orchestrator.list_instances()
    console.print_json(
        data={
            "active_only": active_only,
            "instances": [instance.model_dump(mode="json") for instance in instances],
        }
    )


@app.command("orchestrator-execute")
def orchestrator_execute(
    flow_id: str | None = typer.Option(None, "--flow-id", help="Flow id to resolve to a process."),
    process_id: str | None = typer.Option(None, "--process-id", help="Process id to execute directly."),
    instance_id: str | None = typer.Option(None, "--instance-id", help="Existing instance id to resume."),
    resume_from_node_id: str | None = typer.Option(None, "--resume-from-node-id", help="Node id to resume from."),
    data: str = typer.Option("{}", "--data", help="JSON object with process data."),
    use_langgraph: bool = typer.Option(True, "--langgraph/--linear", help="Use LangGraph workflow execution."),
) -> None:
    """Execute or resume a process and print workflow trace."""
    try:
        payload = json.loads(data)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"--data must be a JSON object: {exc}") from exc
    orchestration_executor = build_orchestration_executor_service()
    result = orchestration_executor.execute(
        OrchestrationExecutionRequest(
            flow_id=flow_id,
            process_id=process_id,
            instance_id=instance_id,
            data=payload,
            resume_from_node_id=resume_from_node_id,
            use_langgraph=use_langgraph,
        )
    )
    console.print_json(data=result.model_dump(mode="json"))


@app.command("orchestrator-validate-definitions")
def orchestrator_validate_definitions() -> None:
    """Validate flow/process YAML definitions against the orchestrator node policy."""
    orchestration_executor = build_orchestration_executor_service()
    report = orchestration_executor.validate_loaded_definitions()
    if not report.get("enabled"):
        console.print_json(data=report)
        return
    has_errors = bool(report.get("errors"))
    console.print_json(data=report)
    if has_errors:
        raise typer.Exit(1)


@app.command("assets-list")
def assets_list(
    asset_type: str | None = typer.Option(None, "--type", help="Filter by asset type."),
    all_statuses: bool = typer.Option(False, "--all-statuses", help="Include draft, candidate, rejected, and deprecated assets."),
) -> None:
    """List enterprise assets from the configured repositories."""
    repository = build_enterprise_asset_repository()
    assets = repository.list_assets(asset_type=asset_type, approved_only=not all_statuses)
    console.print_json(
        data={
            "asset_type": asset_type,
            "approved_only": not all_statuses,
            "assets": [asset.model_dump(mode="json") for asset in assets],
        }
    )


@app.command("assets-show")
def assets_show(asset_id: str) -> None:
    """Show one enterprise asset by id."""
    repository = build_enterprise_asset_repository()
    asset = repository.get(asset_id)
    if asset is None:
        console.print(f"[bold red]Asset not found[/bold red]: {asset_id}")
        raise typer.Exit(1)
    console.print_json(data=asset.model_dump(mode="json"))


@app.command("assets-search")
def assets_search(
    query: str,
    asset_type: list[str] | None = typer.Option(None, "--type", help="Asset type filter. Can be repeated."),
    full: bool = typer.Option(False, "--full", help="Print full asset payloads instead of a compact summary."),
) -> None:
    """Search approved enterprise assets."""
    service = build_asset_search_service()
    result = service.search(query, asset_types=asset_type or None)
    if full:
        console.print_json(data=result.model_dump(mode="json"))
        return
    console.print_json(
        data={
            "query": result.query,
            "primary_assets": [_asset_summary(asset) for asset in result.primary_assets],
            "supporting_assets": [_asset_summary(asset) for asset in result.supporting_assets],
            "evidence_assets": [_asset_summary(asset) for asset in result.evidence_assets],
        }
    )


@app.command("assets-validate")
def assets_validate() -> None:
    """Validate enterprise asset configuration and relations."""
    result = build_asset_validation_service().validate()
    console.print_json(data=result.to_dict())
    if not result.valid:
        raise typer.Exit(1)


@app.command("assets-sync")
def assets_sync() -> None:
    """Write a processed asset index for graph/vector loaders."""
    result = build_asset_sync_service().sync()
    console.print_json(data=result.to_dict())


def _asset_summary(asset) -> dict:
    return {
        "asset_id": asset.asset_id,
        "asset_type": asset.asset_type,
        "name": asset.name,
        "status": asset.status,
        "data_file": _asset_data_file(asset),
        "data_format": _asset_data_format(_asset_data_file(asset)),
        "relations": [relation.model_dump(mode="json") for relation in asset.relations[:4]],
    }
