from __future__ import annotations

from app.knowledge_base.models import AssetRelation, EnterpriseAsset
from app.models import KnowledgeRecord, ProcessDefinition


class FlowAssetAdapter:
    def adapt(self, record: KnowledgeRecord) -> EnterpriseAsset:
        relations = [
            AssetRelation(type="decomposes_to_user_task", target_asset_id=f"user_task.{task.task}")
            for task in record.user_tasks
        ]
        return EnterpriseAsset(
            asset_id=f"flow.{record.flow_id}",
            asset_type="flow",
            name=record.flow_name,
            version="1.0.0",
            status="approved",
            description=record.explanation,
            tags=[*record.concepts, record.intent],
            source_refs=[record.source] if record.source else [],
            relations=relations,
            payload=record.model_dump(mode="json"),
        )


class ProcessAssetAdapter:
    def adapt(self, process: ProcessDefinition) -> EnterpriseAsset:
        relations = [
            AssetRelation(type="implements_flow", target_asset_id=f"flow.{flow_id}")
            for flow_id in process.related_flow_ids
        ]
        relations.extend(
            AssetRelation(type="has_node", target_asset_id=f"process_node.{node.node_id}")
            for node in process.execution_nodes
        )
        return EnterpriseAsset(
            asset_id=f"process.{process.process_id}",
            asset_type="process",
            name=process.process_name,
            version=process.version,
            status=process.status,
            owner=process.owner,
            description=process.description,
            tags=[process.domain, *process.triggers],
            source_refs=[process.metadata["source_path"]] if process.metadata.get("source_path") else [],
            relations=relations,
            payload=process.model_dump(mode="json"),
        )
