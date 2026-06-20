#!/usr/bin/env python3
"""Reset and load knowledge-base engines directly from raw corpus."""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any

from app.config.settings import load_settings
from app.factory import build_enterprise_asset_registry
from app.ingestion.asset_pipeline import CanonicalAssetPipeline
from app.ingestion.federated_topology import FederatedKnowledgeTopology
from app.ingestion.llm_flow_loader import CorpusFlowLoader, OpenAICompatibleLLMClient
from app.ingestion.orchestrator import RoleBasedExtractionInstructionBuilder
from app.ingestion.relation_normalization import RelationNormalizationService, RelationRegistry
from app.knowledge_base.adapters.document import SQLiteDocumentKnowledgeBaseAdapter
from app.knowledge_base.adapters.graph.neo4j import Neo4jKnowledgeBaseGraphAdapter
from app.knowledge_base.adapters.vector.qdrant import QdrantKnowledgeBaseVectorAdapter
from app.knowledge_base.concept_alias_sync import ConceptAliasSyncService
from app.knowledge_base.catalog_store import AssetCatalogStore
from app.knowledge_base.models import EnterpriseAsset
from app.knowledge_base.repository import EnterpriseAssetRepository
from app.knowledge_base.service import KnowledgeBaseService
from app.models import KnowledgeRecord, Task, UserTask
from app.orchestrator.executable_definition_writer import ExecutableDefinitionWriter


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clear", action="store_true", help="Clear KB engines before loading.")
    parser.add_argument("--skip-graph", action="store_true", help="Do not load Neo4j.")
    parser.add_argument("--skip-vector", action="store_true", help="Do not load Qdrant.")
    parser.add_argument("--raw-dir", default="data/raw", help="Raw corpus directory to ingest.")
    parser.add_argument("--model", default=None, help="LLM model for raw corpus asset extraction.")
    parser.add_argument("--build-extraction-instructions", action="store_true", help="Build role-based extraction instructions.")
    args = parser.parse_args()
    summary = reset_load_knowledge_bases(
        raw_dir=args.raw_dir,
        clear=args.clear,
        skip_graph=args.skip_graph,
        skip_vector=args.skip_vector,
        model=args.model,
        build_extraction_instructions=args.build_extraction_instructions,
    )
    print(summary)


def reset_load_knowledge_bases(
    *,
    raw_dir: str = "data/raw",
    clear: bool = False,
    skip_graph: bool = False,
    skip_vector: bool = False,
    model: str | None = None,
    build_extraction_instructions: bool = False,
) -> dict[str, Any]:
    """Load raw corpus documents directly into catalog and knowledge bases."""
    settings = load_settings()
    registry = build_enterprise_asset_registry()
    topology = FederatedKnowledgeTopology.from_yaml(settings.federated_topology_path)
    relation_registry = RelationRegistry.from_yaml(settings.relation_registry_path)
    loader = CorpusFlowLoader(
        OpenAICompatibleLLMClient(
            model=model,
            timeout_seconds=settings.intent_llm_timeout_seconds,
        ),
        instruction_builder=(
            RoleBasedExtractionInstructionBuilder()
            if build_extraction_instructions
            else None
        ),
    )
    raw_path = Path(raw_dir)
    documents = loader.load_corpus(raw_path)
    extraction = loader.extract_documents(documents)
    records = _records_from_extraction(extraction)
    catalog = AssetCatalogStore(settings.processed_directory / "knowledge_base" / "asset_catalog.sqlite")
    document_kb = SQLiteDocumentKnowledgeBaseAdapter(settings.processed_directory / "knowledge_base" / "document_kb.sqlite")
    vector = None
    relation_normalizer = None
    if not skip_vector:
        vector = QdrantKnowledgeBaseVectorAdapter(
            host=os.getenv("QDRANT_HOST", settings.qdrant_host),
            api_key=os.getenv("QDRANT_API_KEY", settings.qdrant_api_key),
        )
        if clear:
            _clear_federated_vector_collections(vector, topology)
        relation_normalizer = RelationNormalizationService(
            relation_registry,
            vector_memory=vector,
            memory_collection=topology.memory_collections.relation_alias_memory,
        )
        relation_normalizer.seed_vector_memory()
    existing_repository = (
        EnterpriseAssetRepository.from_catalog_store(catalog)
        if catalog.path.exists() and not clear
        else EnterpriseAssetRepository([])
    )
    assets = CanonicalAssetPipeline(
        registry=registry,
        relation_pattern_path=settings.relation_pattern_path,
        repository=existing_repository,
        llm_client=loader.llm_client,
        relation_normalizer=relation_normalizer,
        ontology_path=settings.ontology_layers_path,
    ).run(documents=documents, extraction=extraction, records=records)
    assets = _attach_federated_routes(assets, topology, registry)
    written_definition_files = ExecutableDefinitionWriter(
        flow_directory=settings.flow_definition_directory,
        process_directory=settings.process_definition_directory,
    ).emit_from_extraction(extraction=extraction, assets=assets)
    catalog.initialize(clear=False)
    if clear:
        catalog.clear_unmanaged_assets()
    document_kb.initialize(clear=clear)

    for asset in assets:
        catalog.upsert_asset(asset, registry)
        if _should_store_document(asset):
            route = topology.route_asset(asset, registry)
            document_kb.upsert_document(route.document_collection, asset.asset_id, _asset_document_payload(asset, raw_dir))

    graph_loaded = 0
    if not skip_graph:
        graph = Neo4jKnowledgeBaseGraphAdapter(
            neo4j_uri=os.getenv("NEO4J_URI", settings.neo4j_uri),
            neo4j_user=os.getenv("NEO4J_USER", settings.neo4j_user),
            neo4j_password=os.getenv("NEO4J_PASSWORD", settings.neo4j_password),
        )
        graph.initialize()
        if clear:
            graph.clear()
        KnowledgeBaseService(graph).ingest(records)
        for asset in assets:
            graph.upsert_asset(asset)
        graph_loaded = len(records)

    vector_loaded = 0
    alias_memory_loaded = 0
    relation_memory_loaded = 0
    federated_vector_collections_loaded = 0
    concept_aliases_sync = None
    if vector is not None:
        vector_records_by_collection = topology.build_federated_vector_records(assets, registry)
        alias_records = topology.build_alias_memory_records(assets)
        relation_records = topology.build_relation_memory_records(assets)
        if alias_records:
            vector.upsert_texts(topology.memory_collections.asset_alias_memory, alias_records)
            alias_memory_loaded = len(alias_records)
        if relation_records:
            vector.upsert_texts(topology.memory_collections.relation_alias_memory, relation_records)
            relation_memory_loaded = len(relation_records)
        for collection, records_for_collection in vector_records_by_collection.items():
            vector.upsert_texts(collection, records_for_collection)
            federated_vector_collections_loaded += 1
            if collection == topology.memory_collections.global_asset_index:
                vector_loaded = len(records_for_collection)
        concept_aliases_sync = ConceptAliasSyncService(
            concept_aliases_path=settings.project_root / "config" / "knowledge_base" / "concept_aliases.yaml",
            vector_adapter=vector,
        ).sync_from_catalog(catalog)

    return {
        "mode": "raw_corpus_to_knowledge_bases",
        "raw_dir": raw_dir,
        "source_documents": len(documents),
        "assets_loaded": len(assets),
        "flows_loaded": len(extraction["flows"]),
        "user_tasks_loaded": len(extraction["user_tasks"]),
        "tools_loaded": len(extraction["tool_registry"]),
        "business_rules_loaded": len([asset for asset in assets if asset.asset_type == "business_rule"]),
        "rulesets_loaded": len([asset for asset in assets if asset.asset_type == "ruleset"]),
        "processes_loaded": len([asset for asset in assets if asset.asset_type == "process"]),
        "plans_loaded": len([asset for asset in assets if asset.asset_type == "plan"]),
        "asset_sets_loaded": len([asset for asset in assets if asset.asset_type == "asset_set"]),
        "causalities_loaded": len([asset for asset in assets if asset.asset_type == "causality"]),
        "entities_loaded": len([asset for asset in assets if asset.asset_type == "entity"]),
        "qas_loaded": len([asset for asset in assets if asset.asset_type == "qa"]),
        "configurations_loaded": len([asset for asset in assets if asset.asset_type == "configuration"]),
        "catalog": str(catalog.path),
        "document_kb": str(document_kb.path),
        "graph_records_loaded": graph_loaded,
        "vector_records_loaded": vector_loaded,
        "alias_memory_loaded": alias_memory_loaded,
        "relation_memory_loaded": relation_memory_loaded,
        "federated_vector_collections_loaded": federated_vector_collections_loaded,
        "concept_aliases_synced": bool(concept_aliases_sync.updated) if concept_aliases_sync is not None else False,
        "concept_aliases_added": concept_aliases_sync.added_aliases if concept_aliases_sync is not None else 0,
        "concept_aliases_skipped_existing": concept_aliases_sync.skipped_existing if concept_aliases_sync is not None else 0,
        "concept_aliases_skipped_ambiguous": concept_aliases_sync.skipped_ambiguous if concept_aliases_sync is not None else 0,
        "concept_aliases_skipped_low_score": concept_aliases_sync.skipped_low_score if concept_aliases_sync is not None else 0,
        "concept_aliases_skipped_no_match": concept_aliases_sync.skipped_no_match if concept_aliases_sync is not None else 0,
        "intermediate_files_written": len(written_definition_files),
    }


def _records_from_extraction(extraction: dict[str, Any]) -> list[KnowledgeRecord]:
    tasks_by_id = {
        item["user_task_id"]: _user_task_from_payload(item)
        for item in extraction["user_tasks"]
    }
    records = []
    for flow in extraction["flows"]:
        user_tasks = [
            tasks_by_id[ref]
            for ref in flow["user_task_refs"]
            if ref in tasks_by_id
        ]
        records.append(
            KnowledgeRecord(
                flow_id=flow["flow_id"],
                flow_name=flow["flow_name"],
                intent=flow["intent"],
                confidence=flow["confidence"],
                business_event=flow["business_event"],
                utterances=flow["utterances"],
                plan=flow["plan"],
                tasks=[Task(task=task.task, type=task.type) for task in user_tasks],
                user_tasks=user_tasks,
                capabilities=flow["capabilities"],
                concepts=flow["concepts"],
                concept_aliases=flow["concept_aliases"],
                explanation=flow["explanation"],
                source=flow["source"],
                metadata=flow["metadata"],
            )
        )
    return records


def _user_task_from_payload(payload: dict[str, Any]) -> UserTask:
    return UserTask(
        user_task_id=payload["user_task_id"],
        task=payload["task"],
        type=payload["type"],
        name=payload["name"],
        description=payload["description"],
        tools=payload["tools"],
    )

def _should_store_document(asset: EnterpriseAsset) -> bool:
    return asset.asset_type in {
        "business_rule",
        "rule",
        "ruleset",
        "qa",
        "document",
        "configuration",
        "plan",
        "asset_set",
        "causality",
    }


def _asset_document_payload(asset: EnterpriseAsset, raw_dir: str) -> dict:
    payload = asset.model_dump(mode="json")
    payload["raw_dir"] = raw_dir
    payload["document_text"] = _asset_text(asset)
    return payload


def _attach_federated_routes(
    assets: list[EnterpriseAsset],
    topology: FederatedKnowledgeTopology,
    registry,
) -> list[EnterpriseAsset]:
    routed_assets: list[EnterpriseAsset] = []
    for asset in assets:
        route = topology.route_asset(asset, registry)
        routed_assets.append(
            asset.model_copy(
                update={
                    "payload": {
                        **asset.payload,
                        "federated_route": {
                            "owner_kb": route.owner_kb,
                            "vector_collection": route.vector_collection,
                            "document_collection": route.document_collection,
                            "graph_namespace": route.graph_namespace,
                            "alias_memory_collection": route.alias_memory_collection,
                            "relation_memory_collection": route.relation_memory_collection,
                        },
                    }
                }
            )
        )
    return routed_assets


def _clear_federated_vector_collections(
    vector: QdrantKnowledgeBaseVectorAdapter,
    topology: FederatedKnowledgeTopology,
) -> None:
    collections = {
        topology.memory_collections.global_asset_index,
        topology.memory_collections.asset_alias_memory,
        topology.memory_collections.relation_alias_memory,
        topology.memory_collections.evidence_memory,
        *[kb.vector_collection for kb in topology.knowledge_bases.values()],
    }
    for collection in collections:
        vector.clear_collection(collection)


def _asset_text(asset: EnterpriseAsset) -> str:
    values = [
        asset.asset_id,
        asset.asset_type,
        asset.name or "",
        asset.description,
        asset.text,
        " ".join(asset.tags),
        " ".join(asset.source_refs),
    ]
    if asset.payload:
        values.append(str(asset.payload))
    return "\n".join(value for value in values if value)


def _slug(value: Any) -> str:
    text = str(value).strip().lower()
    text = re.sub(r"[^a-z0-9_]+", "_", text)
    return re.sub(r"_+", "_", text).strip("_")


def _operation_name(value: Any) -> str:
    text = str(value).strip().lower()
    text = re.sub(r"[^a-z0-9_.]+", ".", text)
    return re.sub(r"\.+", ".", text).strip(".")


if __name__ == "__main__":
    main()
