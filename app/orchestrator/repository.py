from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.models import (
    OrchestratorInstance,
    OrchestratorJob,
    ProcessExecutionEvent,
    ProcessExecutionResult,
)
from app.orchestrator.providers import OrchestratorEventSink, OrchestratorRepository


@dataclass
class InMemoryOrchestratorRepository(OrchestratorRepository):
    """In-memory repository for process instances and pending jobs."""

    instances: dict[str, OrchestratorInstance] = field(init=False, default_factory=dict)
    jobs: dict[str, OrchestratorJob] = field(init=False, default_factory=dict)
    executions: list[dict] = field(init=False, default_factory=list)

    def save_instance(self, instance: OrchestratorInstance) -> None:
        """Store the latest version of one process instance."""
        self.instances[instance.instance_id] = instance

    def get_instance(self, instance_id: str) -> OrchestratorInstance | None:
        """Return one process instance by id, if present."""
        return self.instances.get(instance_id)

    def list_instances(self, status: str | None = None) -> list[OrchestratorInstance]:
        """List instances, optionally filtered by runtime status."""
        instances = list(self.instances.values())
        if status:
            instances = [instance for instance in instances if instance.status == status]
        return sorted(instances, key=lambda item: item.updated_at, reverse=True)

    def save_job(self, job: OrchestratorJob) -> None:
        """Store a pending or updated orchestrator job."""
        self.jobs[job.job_id] = job

    def list_pending_jobs(self) -> list[OrchestratorJob]:
        """Return all jobs still waiting to run."""
        return [job for job in self.jobs.values() if job.status == "pending"]

    def save_execution(self, flow_id: str | None, result: ProcessExecutionResult) -> None:
        self.executions.append(
            {
                **result.model_dump(mode="json"),
                "flow_id": flow_id,
                "created_at": datetime.now(UTC).isoformat(),
            }
        )

    def list_executions(self, flow_id: str | None = None, limit: int = 20) -> list[dict]:
        values = self.executions
        if flow_id:
            values = [item for item in values if item.get("flow_id") == flow_id]
        return values[-limit:]


@dataclass
class InMemoryOrchestratorEventSink(OrchestratorEventSink):
    """In-memory sink for process execution events."""

    events: list[tuple[str, ProcessExecutionEvent]] = field(default_factory=list)

    def record(self, instance: OrchestratorInstance, event: ProcessExecutionEvent) -> None:
        """Append one event for the given process instance."""
        self.events.append((instance.instance_id, event))


@dataclass
class FileOrchestratorRepository(InMemoryOrchestratorRepository):
    """Persist the active orchestrator registry without using LangGraph checkpoints."""

    path: Path = Path("data/processed/orchestrator_state.json")

    def __post_init__(self) -> None:
        """Load persisted orchestrator state after dataclass construction."""
        self._load()

    def save_instance(self, instance: OrchestratorInstance) -> None:
        super().save_instance(instance)
        self._save()

    def save_job(self, job: OrchestratorJob) -> None:
        super().save_job(job)
        self._save()

    def _load(self) -> None:
        if not self.path.exists():
            return
        data = json.loads(self.path.read_text(encoding="utf-8"))
        self.instances = {
            item["instance_id"]: OrchestratorInstance.model_validate(item)
            for item in data.get("instances", [])
        }
        self.jobs = {
            item["job_id"]: OrchestratorJob.model_validate(item)
            for item in data.get("jobs", [])
        }

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "instances": [instance.model_dump(mode="json") for instance in self.instances.values()],
            "jobs": [job.model_dump(mode="json") for job in self.jobs.values()],
        }
        self.path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


@dataclass
class Neo4jOrchestratorRepository(OrchestratorRepository):
    """Persist orchestrator runtime state and execution history in Neo4j."""

    driver: Any

    def initialize(self) -> None:
        with self.driver.session() as session:
            session.run(
                "CREATE CONSTRAINT IF NOT EXISTS FOR (i:OrchestratorInstance) "
                "REQUIRE i.instance_id IS UNIQUE"
            )
            session.run(
                "CREATE CONSTRAINT IF NOT EXISTS FOR (j:OrchestratorJob) "
                "REQUIRE j.job_id IS UNIQUE"
            )
            session.run(
                "CREATE CONSTRAINT IF NOT EXISTS FOR (e:OrchestrationExecution) "
                "REQUIRE e.execution_id IS UNIQUE"
            )

    def save_instance(self, instance: OrchestratorInstance) -> None:
        payload = instance.model_dump(mode="json")
        with self.driver.session() as session:
            session.run(
                """
                MERGE (instance:OrchestratorInstance {instance_id: $instance_id})
                SET instance.definition_type = $definition_type,
                    instance.definition_id = $definition_id,
                    instance.status = $status,
                    instance.current_node_id = $current_node_id,
                    instance.updated_at = $updated_at,
                    instance.payload_json = $payload_json
                """,
                {
                    "instance_id": instance.instance_id,
                    "definition_type": instance.definition_type,
                    "definition_id": instance.definition_id,
                    "status": instance.status,
                    "current_node_id": instance.current_node_id,
                    "updated_at": instance.updated_at.isoformat(),
                    "payload_json": json.dumps(payload, ensure_ascii=False),
                },
            )

    def get_instance(self, instance_id: str) -> OrchestratorInstance | None:
        with self.driver.session() as session:
            row = session.run(
                "MATCH (instance:OrchestratorInstance {instance_id: $instance_id}) "
                "RETURN instance.payload_json AS payload_json",
                {"instance_id": instance_id},
            ).single()
        return self._instance_from_row(row)

    def list_instances(self, status: str | None = None) -> list[OrchestratorInstance]:
        where = "WHERE instance.status = $status" if status else ""
        parameters = {"status": status} if status else {}
        with self.driver.session() as session:
            rows = session.run(
                f"""
                MATCH (instance:OrchestratorInstance)
                {where}
                RETURN instance.payload_json AS payload_json
                ORDER BY instance.updated_at DESC
                """,
                parameters,
            )
            return [
                instance
                for row in rows
                if (instance := self._instance_from_row(row)) is not None
            ]

    def save_job(self, job: OrchestratorJob) -> None:
        payload = job.model_dump(mode="json")
        with self.driver.session() as session:
            session.run(
                """
                MERGE (job:OrchestratorJob {job_id: $job_id})
                SET job.process_id = $process_id,
                    job.instance_id = $instance_id,
                    job.status = $status,
                    job.payload_json = $payload_json
                WITH job
                MATCH (instance:OrchestratorInstance {instance_id: $instance_id})
                MERGE (instance)-[:HAS_JOB]->(job)
                """,
                {
                    "job_id": job.job_id,
                    "process_id": job.process_id,
                    "instance_id": job.instance_id,
                    "status": job.status,
                    "payload_json": json.dumps(payload, ensure_ascii=False),
                },
            )

    def list_pending_jobs(self) -> list[OrchestratorJob]:
        with self.driver.session() as session:
            rows = session.run(
                "MATCH (job:OrchestratorJob {status: 'pending'}) "
                "RETURN job.payload_json AS payload_json"
            )
            return [
                OrchestratorJob.model_validate(json.loads(str(row["payload_json"])))
                for row in rows
            ]

    def save_execution(self, flow_id: str | None, result: ProcessExecutionResult) -> None:
        execution_id = str(uuid4())
        created_at = datetime.now(UTC).isoformat()
        payload = {
            **result.model_dump(mode="json"),
            "flow_id": flow_id,
            "execution_id": execution_id,
            "created_at": created_at,
        }
        with self.driver.session() as session:
            session.run(
                """
                CREATE (execution:OrchestrationExecution {
                    execution_id: $execution_id,
                    flow_id: $flow_id,
                    process_id: $process_id,
                    instance_id: $instance_id,
                    status: $status,
                    created_at: $created_at,
                    payload_json: $payload_json
                })
                WITH execution
                OPTIONAL MATCH (instance:OrchestratorInstance {instance_id: $instance_id})
                FOREACH (_ IN CASE WHEN instance IS NULL THEN [] ELSE [1] END |
                    MERGE (instance)-[:HAS_EXECUTION]->(execution)
                )
                """,
                {
                    "execution_id": execution_id,
                    "flow_id": flow_id,
                    "process_id": result.process_id,
                    "instance_id": result.instance_id,
                    "status": result.status,
                    "created_at": created_at,
                    "payload_json": json.dumps(payload, ensure_ascii=False),
                },
            )

    def list_executions(self, flow_id: str | None = None, limit: int = 20) -> list[dict]:
        where = "WHERE execution.flow_id = $flow_id" if flow_id else ""
        parameters: dict[str, Any] = {"limit": limit}
        if flow_id:
            parameters["flow_id"] = flow_id
        with self.driver.session() as session:
            rows = session.run(
                f"""
                MATCH (execution:OrchestrationExecution)
                {where}
                RETURN execution.payload_json AS payload_json
                ORDER BY execution.created_at DESC
                LIMIT $limit
                """,
                parameters,
            )
            values = [json.loads(str(row["payload_json"])) for row in rows]
        values.reverse()
        return values

    @staticmethod
    def _instance_from_row(row: Any) -> OrchestratorInstance | None:
        if row is None or not row.get("payload_json"):
            return None
        return OrchestratorInstance.model_validate(json.loads(str(row["payload_json"])))
