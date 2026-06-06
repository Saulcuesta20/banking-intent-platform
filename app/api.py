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
    build_launcher_runtime_service,
    build_orchestration_executor_service,
    build_orchestrator_asset_registry,
    build_orchestrator_service,
)
from app.orchestrator.orchestration_executor import OrchestrationExecutionRequest
from tools.kb_reset_load import reset_load_knowledge_bases


class AskRequest(BaseModel):
    question: str


class IngestRequest(BaseModel):
    source_path: str


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
    path: str = "app/launcher/modules"


class AssetDocumentValidateRequest(BaseModel):
    document: dict[str, Any]
    expected_asset_id: str | None = None
    expected_asset_type: str | None = None


class AssetDraftVersionRequest(BaseModel):
    base_version: str | None = None
    new_version: str | None = None
    actor: str = "saul"
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
        return {
            "environment": environment,
            "asset_types": sorted({str(asset["asset_type"]) for asset in assets}),
            "knowledge_bases": sorted({store for asset in assets for store in asset.get("stores") or []}),
            "statuses": sorted({str(asset["status"]) for asset in assets}),
            "tags": sorted({tag for asset in assets for tag in asset.get("tags") or []}),
            "domains": sorted({str(asset["domain_id"]) for asset in assets if asset.get("domain_id")}),
            "modules": sorted({str(asset["module_id"]) for asset in assets if asset.get("module_id")}),
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
        assets = asset_catalog.list_catalog_assets(
            environment=environment,
            query=query,
            asset_type=asset_type,
            knowledge_base=knowledge_base,
            status=status,
            tag=tag,
            active_only=active_only,
            limit=min(limit, 2_000),
        )
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
            values = asset_set_service.load_directory(Path(request.path))
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
            result = reset_load_knowledge_bases(
                raw_dir=request.source_path,
                clear=False,
            )
            return {"status": "ok", "source": request.source_path, **result}
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
    """Group canonical catalog assets by their configured KB projections."""
    stores = ["graph", "vector", "document", "relational", "repository"]
    tree = []
    for store in stores:
        projected = [asset for asset in assets if store in (asset.get("stores") or [])]
        if not projected:
            continue
        asset_sets: dict[str, list[dict[str, Any]]] = {}
        for asset in projected:
            key = str(asset.get("asset_set_id") or "unassigned")
            asset_sets.setdefault(key, []).append(asset)
        tree.append(
            {
                "id": f"kb:{store}",
                "label": f"{store.title()} KB",
                "kind": "knowledge_base",
                "count": len(projected),
                "children": [
                    {
                        "id": f"asset-set:{asset_set_id}:{store}",
                        "label": asset_set_id,
                        "kind": "asset_set",
                        "count": len(members),
                        "children": [
                            {
                                "id": f"asset:{asset['asset_id']}:{asset['version']}:{store}",
                                "label": asset.get("name") or asset["asset_id"],
                                "kind": "asset",
                                "asset_id": asset["asset_id"],
                                "asset_type": asset["asset_type"],
                                "version": asset["version"],
                                "status": asset["status"],
                                "tags": asset.get("tags") or [],
                                "active": asset.get("active") is True,
                                "children": [],
                            }
                            for asset in members
                        ],
                    }
                    for asset_set_id, members in sorted(asset_sets.items())
                ],
            }
        )
    return tree
