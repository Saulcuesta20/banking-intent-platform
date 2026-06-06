from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.knowledge_base.repository import EnterpriseAssetRepository
from app.knowledge_base.service import KnowledgeBaseService
from app.models import KnowledgeRecord, ProcessDefinition


@dataclass
class OrchestratorAssetRegistry:
    """Formal registry for flow and process assets known by the orchestrator."""

    knowledge_base_service: KnowledgeBaseService
    asset_repository: EnterpriseAssetRepository

    def list_assets(self) -> dict[str, Any]:
        """Return flow/process assets and their orchestration links."""
        flows = self._flows()
        processes = self._processes()
        flow_assets = self._dedupe_assets(
            [self._flow_asset(flow, processes) for flow in flows],
            key="flow_id",
        )
        process_assets = self._dedupe_assets(
            [self._process_asset(process) for process in processes],
            key="process_id",
        )
        return {
            "flows": flow_assets,
            "processes": process_assets,
            "links": self._links(flows, processes),
        }

    def _flows(self) -> list[KnowledgeRecord]:
        repository = self.knowledge_base_service.repository
        if hasattr(repository, "list_all_records"):
            return repository.list_all_records()
        return self.knowledge_base_service.search([])

    def _processes(self) -> list[ProcessDefinition]:
        values = []
        for asset in self.asset_repository.list_assets("process"):
            try:
                values.append(ProcessDefinition(**asset.payload))
            except ValueError:
                continue
        return values

    def _flow_asset(self, flow: KnowledgeRecord, processes: list[ProcessDefinition]) -> dict[str, Any]:
        related_processes = [
            process.process_id
            for process in processes
            if flow.flow_id in process.related_flow_ids
        ]
        return {
            "asset_type": "flow",
            "flow_id": flow.flow_id,
            "flow_name": flow.flow_name,
            "intent": flow.intent,
            "business_event": flow.business_event,
            "source_path": flow.metadata.get("source_path"),
            "source_type": "catalog",
            "plan_steps": len(flow.plan),
            "user_tasks": [task.task for task in flow.user_tasks],
            "related_process_ids": related_processes,
        }

    def _process_asset(self, process: ProcessDefinition, source_type: str = "catalog") -> dict[str, Any]:
        return {
            "asset_type": "process",
            "process_id": process.process_id,
            "process_name": process.process_name,
            "version": process.version,
            "status": process.status,
            "domain": process.domain,
            "source_path": process.metadata.get("source_path"),
            "source_type": source_type,
            "related_flow_ids": process.related_flow_ids,
            "execution_nodes": [
                {
                    "node_id": node.node_id,
                    "type": node.type,
                    "name": node.name,
                    "implementation": node.implementation,
                }
                for node in process.execution_nodes
            ],
            "transitions": [
                {
                    "from_node": transition.from_node,
                    "to_node": transition.to_node,
                    "condition": transition.condition,
                }
                for transition in process.transitions
            ],
        }

    @staticmethod
    def _dedupe_assets(assets: list[dict[str, Any]], *, key: str) -> list[dict[str, Any]]:
        values: dict[str, dict[str, Any]] = {}
        for asset in assets:
            asset_key = str(asset.get(key) or "")
            if not asset_key:
                continue
            if asset_key not in values or asset.get("source_type") == "yaml":
                values[asset_key] = asset
        return sorted(values.values(), key=lambda asset: str(asset.get(key) or ""))

    def _links(self, flows: list[KnowledgeRecord], processes: list[ProcessDefinition]) -> list[dict[str, str]]:
        flow_ids = {flow.flow_id for flow in flows}
        links = []
        for process in processes:
            for flow_id in process.related_flow_ids:
                if flow_id in flow_ids:
                    links.append({"flow_id": flow_id, "process_id": process.process_id})
        return links
