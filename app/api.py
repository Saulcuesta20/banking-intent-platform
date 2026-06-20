from __future__ import annotations

from pathlib import Path
import json
import re
from typing import Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.factory import (
    build_ask_service,
    build_asset_catalog_store,
    build_asset_set_deployment_service,
    build_enterprise_asset_registry,
    build_ingestion_orchestrator,
    build_knowledge_base_service,
    build_launcher_runtime_service,
    build_orchestration_executor_service,
    build_orchestrator_asset_registry,
    build_orchestrator_service,
)
from app.config.settings import load_settings
from app.ingestion.orchestrator import IngestionOrchestratorConfig
from app.orchestrator.orchestration_executor import OrchestrationExecutionRequest


class AskRequest(BaseModel):
    question: str


class IngestRequest(BaseModel):
    source_path: str
    catalog_only: bool = True


class ExecuteProcessRequest(BaseModel):
    flow_id: str | None = None
    process_id: str | None = None
    instance_id: str | None = None
    data: dict = {}
    resume_from_node_id: str | None = None
    use_langgraph: bool = True


class AssetSetTransitionRequest(BaseModel):
    version: str
    action: str
    actor: str = "saul"
    comment: str | None = None


class AssetSetDeployRequest(BaseModel):
    version: str
    environment: str = "dev"
    actor: str = "saul"


class AssetSetLoadRequest(BaseModel):
    path: str | None = None


class AssetDocumentValidateRequest(BaseModel):
    document: dict[str, Any]
    expected_asset_id: str | None = None
    expected_asset_type: str | None = None


class AssetDraftVersionRequest(BaseModel):
    base_version: str | None = None
    new_version: str | None = None
    actor: str = "saul"
    document: dict[str, Any]


class AssetDraftPreviewRequest(BaseModel):
    base_version: str | None = None
    new_version: str | None = None
    environment: str = "dev"
    document: dict[str, Any]


TRACE_TITLES = {
    "call": "Llamada de servicio",
    "orchestration": "Orquestacion",
    "question_understanding": "Comprension de pregunta",
    "input": "Entrada",
    "knowledge_base": "Consulta de conocimiento",
    "graph": "Consulta al grafo",
    "asset_search": "Busqueda de activos",
    "knowledge_source_router": "Seleccion de fuentes",
    "evidence_bundle": "Evidencia",
    "tools": "Herramientas disponibles",
    "planning": "Razonamiento y plan",
    "intent": "Seleccion de intencion",
    "llm": "Razonamiento LLM",
    "answer": "Construccion de respuesta",
    "approval": "Control de aprobacion",
    "resolution": "Resolucion",
    "audit": "Auditoria",
    "debug_trace": "Registro tecnico",
}

CATALOG_STATUS_ORDER = {
    "ready_for_review": 0,
    "in_review": 1,
    "validated": 2,
    "active": 3,
    "draft": 4,
    "approved": 5,
    "rejected": 6,
    "deprecated": 7,
    "retired": 8,
}

CANONICAL_CATALOG_STATUSES = list(CATALOG_STATUS_ORDER.keys())


def _trace_step(sequence: int, component: str, message: str) -> dict[str, Any]:
    summary = message
    result: str | None = None
    details: dict[str, Any] = {}
    call_match = re.match(
        r"class=(?P<class_name>\S+) method=(?P<method>\S+) (?P<direction>input|output)=(?P<value>.*)",
        message,
    )
    if call_match:
        values = call_match.groupdict()
        direction = values["direction"]
        summary = (
            f"Invocando {values['class_name']}.{values['method']}"
            if direction == "input"
            else f"{values['class_name']}.{values['method']} completado"
        )
        result = _compact_trace_value(values["value"])
        details = {
            "class": values["class_name"],
            "method": values["method"],
            "direction": direction,
        }
    elif message.startswith("query="):
        summary = "Cypher ejecutado contra Neo4j"
        result = "Consulta completada"
    elif message.startswith("params="):
        summary = "Parametros enviados al grafo"
        result = _compact_trace_value(message.removeprefix("params="))
    elif "=" in message:
        key, value = message.split("=", 1)
        summary = key.replace("_", " ").strip().capitalize()
        result = _compact_trace_value(value)
    return {
        "sequence": sequence,
        "component": component,
        "title": TRACE_TITLES.get(component, component.replace("_", " ").title()),
        "summary": summary,
        "result": result,
        "status": "completed",
        "details": details,
    }


def _compact_trace_value(value: str, limit: int = 220) -> str:
    text = value.strip()
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        parsed = None
    if isinstance(parsed, dict):
        preferred = [
            f"{key}: {parsed[key]}"
            for key in (
                "flow_id",
                "selected_flow",
                "intent",
                "confidence",
                "route",
                "can_resolve",
                "business_event",
            )
            if key in parsed
        ]
        text = " | ".join(preferred) if preferred else f"{len(parsed)} campos procesados"
    elif isinstance(parsed, list):
        text = f"{len(parsed)} elementos procesados"
    return text if len(text) <= limit else f"{text[: limit - 3]}..."


def create_app() -> FastAPI:
    app = FastAPI(
        title="Banking Intent Platform",
        description="Enterprise banking answers grounded in an approved knowledge graph.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:3002",
            "http://127.0.0.1:3002",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    orchestrator_service = build_orchestrator_service()
    orchestration_executor = build_orchestration_executor_service(orchestrator_service)
    asset_registry = build_orchestrator_asset_registry()
    launcher_runtime = build_launcher_runtime_service()
    asset_catalog = build_asset_catalog_store()
    asset_set_service = build_asset_set_deployment_service()

    @app.post("/ask")
    def ask(request: AskRequest) -> dict:
        service = build_ask_service()
        try:
            raw_trace_steps: list[tuple[str, str]] = []
            result = service.resolve(
                request.question,
                trace=lambda component, message: raw_trace_steps.append((component, message)),
            )
            trace_steps = [
                _trace_step(index, component, message)
                for index, (component, message) in enumerate(raw_trace_steps, start=1)
            ]
            return {**result.to_dict(), "trace_steps": trace_steps}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @app.get("/launcher/home")
    def launcher_home() -> dict:
        try:
            return launcher_runtime.home()
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @app.get("/launcher/flows/{flow_id}")
    def launcher_flow(flow_id: str) -> dict:
        try:
            return launcher_runtime.flow_context(flow_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @app.get("/catalog/metadata")
    def catalog_metadata(environment: str = "dev") -> dict:
        assets = asset_catalog.list_catalog_assets(environment=environment, status="all", limit=10_000)
        registry = build_enterprise_asset_registry()
        catalog_asset_types = sorted({str(asset["asset_type"]) for asset in assets})
        catalog_statuses = sorted({str(asset["status"]) for asset in assets})
        catalog_tags = sorted({tag for asset in assets for tag in asset.get("tags") or []})
        catalog_domains = sorted({str(asset["domain_id"]) for asset in assets if asset.get("domain_id")})
        catalog_modules = sorted({str(asset["module_id"]) for asset in assets if asset.get("module_id")})
        knowledge_base_values = set()
        for asset in assets:
            for kb in _knowledge_bases_for_asset(asset):
                knowledge_base_values.add(kb)
        knowledge_bases = sorted(knowledge_base_values)
        if not knowledge_bases:
            knowledge_bases = ["catalog"]
        return {
            "environment": environment,
            "asset_types": sorted({*catalog_asset_types, *registry.list_asset_types()}),
            "knowledge_bases": knowledge_bases,
            "statuses": sorted({*catalog_statuses, *CANONICAL_CATALOG_STATUSES}, key=lambda value: CATALOG_STATUS_ORDER.get(value, 999)),
            "tags": catalog_tags,
            "domains": catalog_domains,
            "modules": catalog_modules,
        }

    @app.get("/catalog/assets")
    def catalog_assets(
        environment: str = "dev",
        query: str | None = None,
        asset_type: str | None = None,
        knowledge_base: str | None = None,
        status: str | None = None,
        tag: str | None = None,
        active_only: bool = False,
        limit: int = 500,
    ) -> dict:
        knowledge_base = _normalize_catalog_knowledge_base_filter(knowledge_base)
        kb_filter = _normalize_catalog_knowledge_base_filter(knowledge_base)
        assets = asset_catalog.list_catalog_assets(
            environment=environment,
            query=query,
            asset_type=asset_type,
            knowledge_base=None,  # filter manually so owner-based KBs are included
            status=status,
            tag=tag,
            active_only=active_only,
            limit=min(limit, 2_000),
        )
        if kb_filter:
            assets = [asset for asset in assets if kb_filter in _knowledge_bases_for_asset(asset)]
        return {
            "environment": environment,
            "count": len(assets),
            "assets": assets,
            "tree": _catalog_asset_tree(assets),
        }

    @app.get("/catalog/assets/{asset_id:path}")
    def catalog_asset(asset_id: str, version: str | None = None) -> dict:
        asset = asset_catalog.get_catalog_asset(asset_id, version)
        if asset is None:
            raise HTTPException(status_code=404, detail=f"Catalog asset not found: {asset_id}")
        return asset

    @app.get("/catalog/knowledge-bases/{knowledge_base}/ontology")
    def catalog_ontology(
        knowledge_base: str,
        environment: str = "dev",
        asset_type: str = "entity",
        limit: int = 2_000,
    ) -> dict:
        kb_filter = _normalize_catalog_knowledge_base_filter(knowledge_base)
        assets = asset_catalog.list_catalog_assets(
            environment=environment,
            asset_type=asset_type,
            knowledge_base=None,
            status="all",
            limit=min(limit, 2_000),
        )
        if kb_filter:
            assets = [asset for asset in assets if kb_filter in _knowledge_bases_for_asset(asset)]
        nodes: list[dict[str, Any]] = []
        relation_map: dict[str, dict[str, Any]] = {}
        asset_by_id = {asset["asset_id"]: asset for asset in assets}

        def add_relation(
            *,
            relation_id: str,
            source_asset_id: str,
            target_asset_id: str,
            relation_type: str,
            source_asset: dict[str, Any] | None = None,
            target_asset: dict[str, Any] | None = None,
        ) -> None:
            source_asset = source_asset or asset_by_id.get(source_asset_id) or asset_catalog.get_catalog_asset(source_asset_id)
            target_asset = target_asset or asset_by_id.get(target_asset_id) or asset_catalog.get_catalog_asset(target_asset_id)
            relation_map.setdefault(
                relation_id,
                {
                    "id": relation_id,
                    "source_entity_id": source_asset_id,
                    "target_entity_id": target_asset_id,
                    "relation_type": relation_type,
                    "relation_family": _ontology_relation_family(relation_type),
                    "source_name": (source_asset or {}).get("name"),
                    "source_asset_type": (source_asset or {}).get("asset_type"),
                    "target_name": (target_asset or {}).get("name"),
                    "target_asset_type": (target_asset or {}).get("asset_type"),
                },
            )

        for asset in assets:
            payload = asset.get("payload") or {}
            asset_payload = payload.get("payload") if isinstance(payload.get("payload"), dict) else payload
            entities = payload.get("entities")
            if entities and isinstance(entities, list):
                # Some assets (like ontology) may already include aggregate entities
                for entity in entities:
                    nodes.append(_format_ontology_node(entity, asset))
                continue
            nodes.append(
                {
                    "asset_id": asset["asset_id"],
                    "asset_type": asset.get("asset_type"),
                    "name": asset.get("name"),
                    "description": asset_payload.get("description") or asset_payload.get("definition") or payload.get("description"),
                    "structural_layer": asset.get("structural_layer") or asset_payload.get("structural_layer") or payload.get("structural_layer") or asset_payload.get("business_layer"),
                    "layer": asset.get("structural_layer") or asset_payload.get("structural_layer") or payload.get("structural_layer") or asset_payload.get("business_layer") or asset_payload.get("layer"),
                    "role": asset_payload.get("entity_role") or asset_payload.get("role"),
                    "subtype": asset_payload.get("subtype") or payload.get("subtype"),
                    "technical_type": asset_payload.get("technical_type") or payload.get("technical_type"),
                    "semantic_space": asset.get("semantic_space") or asset_payload.get("semantic_space"),
                    "primary_kb": asset.get("primary_kb"),
                    "aliases": asset_payload.get("aliases") or [],
                    "attributes": asset_payload.get("attributes") or [],
                }
            )
            for relation in asset_catalog.children(asset["asset_id"]):
                target_id = relation["target_asset_id"]
                relation_id = f"{asset['asset_id']}::{relation['relation_type']}::{target_id}"
                add_relation(
                    relation_id=relation_id,
                    source_asset_id=asset["asset_id"],
                    target_asset_id=target_id,
                    relation_type=relation["relation_type"],
                    source_asset=asset,
                    target_asset=relation.get("target"),
                )
            for relation in asset_catalog.find_referencers(asset["asset_id"]):
                source_id = relation["source_asset_id"]
                relation_id = f"{source_id}::{relation['relation_type']}::{asset['asset_id']}"
                add_relation(
                    relation_id=relation_id,
                    source_asset_id=source_id,
                    target_asset_id=asset["asset_id"],
                    relation_type=relation["relation_type"],
                    target_asset=asset,
                )
        return {
            "knowledge_base": knowledge_base,
            "environment": environment,
            "entity_count": len(nodes),
            "relation_count": len(relation_map),
            "entities": nodes,
            "relations": list(relation_map.values()),
        }

    @app.post("/catalog/assets/validate")
    def validate_catalog_asset(request: AssetDocumentValidateRequest) -> dict:
        try:
            return asset_set_service.validate_asset_document(
                document=request.document,
                expected_asset_id=request.expected_asset_id,
                expected_asset_type=request.expected_asset_type,
            )
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc))

    @app.post("/catalog/assets/{asset_id:path}/versions")
    def create_catalog_asset_version(asset_id: str, request: AssetDraftVersionRequest) -> dict:
        try:
            return asset_set_service.create_draft_version(
                asset_id=asset_id,
                base_version=request.base_version,
                document=request.document,
                actor=request.actor,
                new_version=request.new_version,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc))

    @app.post("/catalog/assets/{asset_id:path}/preview")
    def preview_catalog_asset_version(asset_id: str, request: AssetDraftPreviewRequest) -> dict:
        try:
            return asset_set_service.preview_draft_version(
                asset_id=asset_id,
                base_version=request.base_version,
                new_version=request.new_version,
                environment=request.environment,
                document=request.document,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))

    @app.get("/catalog/assets/{asset_id:path}/diff")
    def diff_catalog_asset_versions(asset_id: str, from_version: str, to_version: str) -> dict:
        try:
            return asset_set_service.diff_asset_versions(
                asset_id=asset_id,
                from_version=from_version,
                to_version=to_version,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    @app.get("/catalog/assets/{asset_id:path}/projection-preview")
    def projection_preview_catalog_asset(
        asset_id: str,
        version: str | None = None,
        environment: str = "dev",
    ) -> dict:
        try:
            return asset_set_service.projection_preview(
                asset_id=asset_id,
                version=version,
                environment=environment,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    @app.get("/catalog/asset-sets")
    def catalog_asset_sets(environment: str = "dev", status: str | None = None) -> dict:
        values = asset_catalog.list_asset_sets(environment=environment, status=status)
        return {"environment": environment, "count": len(values), "asset_sets": values}

    @app.get("/catalog/asset-sets/{asset_set_id}/{version}")
    def catalog_asset_set(asset_set_id: str, version: str) -> dict:
        value = asset_catalog.get_asset_set(asset_set_id, version)
        if value is None:
            raise HTTPException(
                status_code=404,
                detail=f"AssetSet version not found: {asset_set_id}@{version}",
            )
        return value

    @app.post("/catalog/asset-sets/load")
    def load_asset_sets(request: AssetSetLoadRequest) -> dict:
        try:
            root = Path(request.path) if request.path else load_settings().asset_source_path
            values = asset_set_service.load_directory(root)
            return {"loaded": len(values), "asset_sets": values}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/catalog/asset-sets/{asset_set_id}/transition")
    def transition_asset_set(asset_set_id: str, request: AssetSetTransitionRequest) -> dict:
        action_status = {
            "submit_review": "ready_for_review",
            "start_review": "in_review",
            "validate": "validated",
            "reject": "rejected",
            "request_changes": "draft",
            "deprecate": "deprecated",
            "retire": "retired",
        }
        to_status = action_status.get(request.action)
        if to_status is None:
            raise HTTPException(status_code=400, detail=f"Unknown lifecycle action: {request.action}")
        if request.action in {"reject", "request_changes"} and not (request.comment or "").strip():
            raise HTTPException(status_code=400, detail="A reviewer comment is required")
        try:
            return asset_catalog.transition_asset_set(
                asset_set_id=asset_set_id,
                version=request.version,
                to_status=to_status,
                actor=request.actor,
                comment=request.comment,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc))

    @app.post("/catalog/asset-sets/{asset_set_id}/deploy")
    def deploy_asset_set(asset_set_id: str, request: AssetSetDeployRequest) -> dict:
        try:
            return asset_set_service.deploy(
                asset_set_id=asset_set_id,
                version=request.version,
                environment=request.environment,
                actor=request.actor,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc))

    @app.post("/catalog/asset-sets/{asset_set_id}/rollback")
    def rollback_asset_set(asset_set_id: str, request: AssetSetDeployRequest) -> dict:
        try:
            return asset_catalog.rollback_asset_set(
                asset_set_id=asset_set_id,
                environment=request.environment,
                actor=request.actor,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc))

    @app.post("/ingest")
    def ingest(request: IngestRequest) -> dict:
        try:
            settings = load_settings()
            result = build_ingestion_orchestrator().run(
                IngestionOrchestratorConfig(
                    raw_path=Path(request.source_path),
                    audit_directory=settings.processed_directory / "ingestion_audit",
                    knowledge_base_service=None if request.catalog_only else build_knowledge_base_service(),
                    asset_catalog_store=asset_catalog,
                    asset_registry=build_enterprise_asset_registry(),
                    apply=True,
                    project_knowledge_bases=not request.catalog_only,
                )
            )
            return {
                "status": "ok",
                "source": request.source_path,
                "flows_persisted": result.flows_persisted,
                "canonical_assets_generated": result.canonical_assets_generated,
                "catalog_assets_persisted": result.catalog_assets_persisted,
                "audit_path": str(result.audit_path),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @app.get("/orchestrator/assets")
    def orchestrator_assets() -> dict:
        try:
            return asset_registry.list_assets()
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @app.get("/orchestrator/instances")
    def orchestrator_instances(active_only: bool = True) -> dict:
        try:
            instances = (
                orchestrator_service.list_active_instances()
                if active_only
                else orchestrator_service.list_instances()
            )
            return {
                "active_only": active_only,
                "instances": [instance.model_dump(mode="json") for instance in instances],
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @app.post("/orchestrator/process/execute")
    def execute_process(request: ExecuteProcessRequest) -> dict:
        try:
            result = orchestration_executor.execute(
                OrchestrationExecutionRequest(
                    flow_id=request.flow_id,
                    process_id=request.process_id,
                    instance_id=request.instance_id,
                    data=dict(request.data or {}),
                    resume_from_node_id=request.resume_from_node_id,
                    use_langgraph=request.use_langgraph,
                )
            )
            orchestrator_service.repository.save_execution(request.flow_id, result)
            return {
                **result.model_dump(mode="json"),
                "flow_id": request.flow_id,
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @app.get("/orchestrator/executions")
    def orchestrator_executions(flow_id: str | None = None) -> dict:
        return {
            "executions": orchestrator_service.repository.list_executions(
                flow_id=flow_id,
                limit=20,
            )
        }

    return app


def _catalog_asset_tree(assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group catalog assets by knowledge base -> asset set -> asset."""

    def _asset_sort_key(asset: dict[str, Any]) -> tuple[int, str, str]:
        status = str(asset.get("status") or "")
        return (
            CATALOG_STATUS_ORDER.get(status, 999),
            str(asset.get("name") or asset.get("asset_id") or ""),
            str(asset.get("asset_id") or ""),
        )

    if not assets:
        return []

    kb_groups: dict[str, list[dict[str, Any]]] = {}
    for asset in assets:
        kbs = _knowledge_bases_for_asset(asset)
        for kb in kbs:
            kb_groups.setdefault(kb, []).append(asset)

    tree: list[dict[str, Any]] = []
    for kb_name in sorted(kb_groups.keys()):
        members = kb_groups[kb_name]
        tree.append(
            {
                "id": f"kb:{kb_name}",
                "label": kb_name,
                "kind": "knowledge_base",
                "count": len(members),
                "children": _catalog_asset_set_nodes(members, suffix=kb_name),
            }
        )

    for node in tree:
        for asset_set_node in node.get("children", []):
            asset_set_node["children"] = sorted(asset_set_node["children"], key=_asset_sort_key)
    return tree


def _catalog_asset_set_nodes(assets: list[dict[str, Any]], *, suffix: str) -> list[dict[str, Any]]:
    asset_sets: dict[str, list[dict[str, Any]]] = {}
    for asset in assets:
        key = str(asset.get("asset_set_id") or "unassigned")
        asset_sets.setdefault(key, []).append(asset)

    nodes: list[dict[str, Any]] = []
    for asset_set_id, members in sorted(asset_sets.items()):
        nodes.append(
            {
                "id": f"asset-set:{asset_set_id}:{suffix}",
                "label": asset_set_id,
                "kind": "asset_set",
                "count": len(members),
                "children": [
                    {
                        "id": f"asset:{asset['asset_id']}:{asset['version']}:{suffix}",
                        "label": asset.get("name") or asset["asset_id"],
                        "kind": "asset",
                        "asset_id": asset["asset_id"],
                        "asset_type": asset["asset_type"],
                        "version": asset["version"],
                        "status": asset["status"],
                        "tags": asset.get("tags") or [],
                        "active": asset.get("active") is True,
                        "primary_kb": asset.get("primary_kb"),
                        "children": [],
                    }
                    for asset in members
                ],
            }
        )
    return nodes


def _normalize_catalog_knowledge_base_filter(value: str | None) -> str | None:
    """Map launcher-facing catalog labels to the underlying catalog query semantics."""
    if not value:
        return None
    normalized = value.strip().lower().replace("-", "_")
    if normalized in {"catalog", "all"}:
        return None
    if normalized in {"repo", "repository"}:
        return "repository"
    return normalized


def _normalize_knowledge_base_name(value: str | None) -> str:
    text = str(value or "catalog").strip()
    return text or "catalog"


def _knowledge_bases_for_asset(asset: dict[str, Any]) -> list[str]:
    values = []
    primary = asset.get("primary_kb")
    if primary:
        values.append(_normalize_knowledge_base_name(primary))
    payload = asset.get("payload") or {}
    owner = payload.get("owner") or payload.get("knowledge_base")
    if owner:
        normalized_owner = _normalize_knowledge_base_name(owner)
        if normalized_owner not in values:
            values.append(normalized_owner)
    if not values:
        values = ["catalog"]
    return values


def _ontology_relation_family(relation_type: str) -> str:
    relation = str(relation_type or "").strip()
    if relation in {"represented_by", "represents", "materializes", "materialized_in"}:
        return "business_technical_mapping"
    if relation in {"contains_context", "routes_to_asset"}:
        return "search_context"
    if relation in {"classifies"}:
        return "classification"
    if relation.startswith("groups_") or relation in {"used_by_flow", "used_by_process", "explained_by_qa", "uses_entity"}:
        return "governance"
    if relation in {"governed_by", "governed_by_rule"}:
        return "governance"
    if relation in {"affects", "increases", "decreases", "related_to", "owned_by", "uses", "supports", "enables"}:
        return "business_fact"
    return "unknown"


def _format_ontology_node(entity: dict[str, Any], asset: dict[str, Any]) -> dict[str, Any]:
    return {
        "asset_id": entity.get("asset_id") or asset.get("asset_id"),
        "asset_type": entity.get("asset_type") or asset.get("asset_type"),
        "name": entity.get("name") or asset.get("name"),
        "description": entity.get("description") or entity.get("definition") or asset.get("description"),
        "structural_layer": entity.get("structural_layer") or entity.get("business_layer") or entity.get("layer"),
        "layer": entity.get("structural_layer") or entity.get("business_layer") or entity.get("layer"),
        "role": entity.get("entity_role") or entity.get("role"),
        "subtype": entity.get("subtype"),
        "technical_type": entity.get("technical_type"),
        "semantic_space": entity.get("semantic_space"),
        "primary_kb": asset.get("primary_kb"),
        "aliases": entity.get("aliases") or [],
        "attributes": entity.get("attributes") or [],
    }
