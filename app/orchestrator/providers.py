from __future__ import annotations

from typing import Protocol

from app.models import OrchestratorInstance, OrchestratorJob, ProcessExecutionEvent


class OrchestratorRepository(Protocol):
    def save_instance(self, instance: OrchestratorInstance) -> None:
        """Persist a long-running flow/process instance."""

    def get_instance(self, instance_id: str) -> OrchestratorInstance | None:
        """Load a flow/process instance by id."""

    def save_job(self, job: OrchestratorJob) -> None:
        """Persist a pending async/timer/message/compensation job."""

    def list_pending_jobs(self) -> list[OrchestratorJob]:
        """Return pending jobs ready for the orchestrator."""


class OrchestratorEventSink(Protocol):
    def record(self, instance: OrchestratorInstance, event: ProcessExecutionEvent) -> None:
        """Record runtime events for audit/listeners."""
