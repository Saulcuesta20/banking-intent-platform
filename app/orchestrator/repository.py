from __future__ import annotations

from app.models import OrchestratorInstance, OrchestratorJob, ProcessExecutionEvent
from app.orchestrator.providers import OrchestratorEventSink, OrchestratorRepository


class InMemoryOrchestratorRepository(OrchestratorRepository):
    def __init__(self):
        self.instances: dict[str, OrchestratorInstance] = {}
        self.jobs: dict[str, OrchestratorJob] = {}

    def save_instance(self, instance: OrchestratorInstance) -> None:
        self.instances[instance.instance_id] = instance

    def get_instance(self, instance_id: str) -> OrchestratorInstance | None:
        return self.instances.get(instance_id)

    def save_job(self, job: OrchestratorJob) -> None:
        self.jobs[job.job_id] = job

    def list_pending_jobs(self) -> list[OrchestratorJob]:
        return [job for job in self.jobs.values() if job.status == "pending"]


class InMemoryOrchestratorEventSink(OrchestratorEventSink):
    def __init__(self):
        self.events: list[tuple[str, ProcessExecutionEvent]] = []

    def record(self, instance: OrchestratorInstance, event: ProcessExecutionEvent) -> None:
        self.events.append((instance.instance_id, event))
