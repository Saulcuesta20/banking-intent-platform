from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from app.models import (
    OrchestratorInstance,
    OrchestratorJob,
    ProcessDefinition,
    ProcessExecutionEvent,
)
from app.orchestrator.providers import OrchestratorEventSink, OrchestratorRepository
from app.orchestrator.repository import InMemoryOrchestratorEventSink, InMemoryOrchestratorRepository


@dataclass
class OrchestratorService:
    """Runtime coordinator for long-running flow and process instances."""

    repository: OrchestratorRepository = field(default_factory=InMemoryOrchestratorRepository)
    event_sink: OrchestratorEventSink = field(default_factory=InMemoryOrchestratorEventSink)

    def start_process_instance(
        self,
        process: ProcessDefinition,
        definition_type: Literal["flow", "process"] = "process",
        definition_id: str | None = None,
        data: dict | None = None,
        correlation_keys: dict[str, str] | None = None,
        parent_instance_id: str | None = None,
    ) -> OrchestratorInstance:
        """Create and persist a running process instance."""
        first_node_id = process.execution_nodes[0].node_id if process.execution_nodes else None
        instance = OrchestratorInstance(
            instance_id=str(uuid4()),
            definition_type=definition_type,
            definition_id=definition_id or process.process_id,
            version=process.version,
            status="running",
            current_node_id=first_node_id,
            parent_instance_id=parent_instance_id,
            correlation_keys=correlation_keys or {},
            data=data or {},
            pending_jobs=[],
        )
        self.repository.save_instance(instance)
        self._record(instance, "process_started", "Process instance started.")
        return instance

    def create_pending_jobs(self, process: ProcessDefinition, instance: OrchestratorInstance) -> OrchestratorInstance:
        """Create pending jobs declared by the process definition."""
        jobs: list[OrchestratorJob] = []
        for definition in process.jobs:
            job = OrchestratorJob(
                job_id=f"{instance.instance_id}:{definition.job_id}",
                process_id=process.process_id,
                instance_id=instance.instance_id,
                node_id=definition.node_id,
                type=definition.type,
                status=definition.status,
                payload=definition.metadata,
            )
            self.repository.save_job(job)
            jobs.append(job)
        updated = instance.model_copy(update={"pending_jobs": [*instance.pending_jobs, *jobs], "updated_at": datetime.now(UTC)})
        self.repository.save_instance(updated)
        return updated

    def correlate_message(
        self,
        instance_id: str,
        message_name: str,
        payload: dict,
    ) -> OrchestratorInstance:
        """Merge an external message payload into a running instance."""
        instance = self._require_instance(instance_id)
        data = {**instance.data, **payload, "_last_message": message_name}
        updated = instance.model_copy(update={"data": data, "status": "running", "updated_at": datetime.now(UTC)})
        self.repository.save_instance(updated)
        self._record(updated, "message_correlated", f"Message correlated: {message_name}")
        return updated

    def mark_waiting(self, instance_id: str, node_id: str, waiting_for: list[str]) -> OrchestratorInstance:
        instance = self._require_instance(instance_id)
        updated = instance.model_copy(
            update={
                "status": "waiting",
                "current_node_id": node_id,
                "data": {**instance.data, "_waiting_for": waiting_for},
                "updated_at": datetime.now(UTC),
            }
        )
        self.repository.save_instance(updated)
        self._record(updated, "process_waiting", f"Waiting for: {', '.join(waiting_for)}")
        return updated

    def complete_instance(self, instance_id: str) -> OrchestratorInstance:
        instance = self._require_instance(instance_id)
        updated = instance.model_copy(update={"status": "completed", "updated_at": datetime.now(UTC)})
        self.repository.save_instance(updated)
        self._record(updated, "process_completed", "Process instance completed.")
        return updated

    def list_instances(self, status: str | None = None) -> list[OrchestratorInstance]:
        return self.repository.list_instances(status=status)

    def list_active_instances(self) -> list[OrchestratorInstance]:
        return [
            instance
            for instance in self.repository.list_instances()
            if instance.status in {"running", "waiting", "compensating"}
        ]

    def _require_instance(self, instance_id: str) -> OrchestratorInstance:
        instance = self.repository.get_instance(instance_id)
        if instance is None:
            raise KeyError(f"Orchestrator instance not found: {instance_id}")
        return instance

    def _record(self, instance: OrchestratorInstance, event_name: str, message: str) -> None:
        event = ProcessExecutionEvent(
            node_id=instance.current_node_id or "orchestrator",
            status="completed",
            message=f"{event_name}: {message}",
        )
        self.event_sink.record(instance, event)
