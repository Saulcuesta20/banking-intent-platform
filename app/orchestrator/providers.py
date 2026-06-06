from __future__ import annotations

from typing import Protocol

from app.models import OrchestratorInstance, OrchestratorJob, ProcessExecutionEvent, ProcessExecutionResult


class OrchestratorRepository(Protocol):
    def save_instance(self, instance: OrchestratorInstance) -> None:
        """Persist a long-running flow/process instance."""

    def get_instance(self, instance_id: str) -> OrchestratorInstance | None:
        """Load a flow/process instance by id."""

    def list_instances(self, status: str | None = None) -> list[OrchestratorInstance]:
        """Return known orchestration instances."""

    def save_job(self, job: OrchestratorJob) -> None:
        """Persist a pending async/timer/message/compensation job."""

    def list_pending_jobs(self) -> list[OrchestratorJob]:
        """Return pending jobs ready for the orchestrator."""

    def save_execution(self, flow_id: str | None, result: ProcessExecutionResult) -> None:
        """Persist one completed or waiting execution result."""

    def list_executions(self, flow_id: str | None = None, limit: int = 20) -> list[dict]:
        """Return recent persisted execution results."""


class OrchestratorEventSink(Protocol):
    def record(self, instance: OrchestratorInstance, event: ProcessExecutionEvent) -> None:
        """Record runtime events for audit/listeners."""
