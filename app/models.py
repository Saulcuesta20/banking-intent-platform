from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field, model_validator


class Action(BaseModel):
    action: str
    type: Literal["front_action", "back_action"]
    operation: str | None = None
    resource: str | None = None
    label: str | None = None
    triggers: str | None = None
    description: str | None = None

    model_config = {"frozen": True}

    def to_dict(self) -> dict[str, str | None]:
        return {
            "action": self.action,
            "type": self.type,
            "operation": self.operation,
            "resource": self.resource,
            "label": self.label,
            "triggers": self.triggers,
            "description": self.description,
        }


class ActionRegistryEntry(BaseModel):
    action: str
    type: Literal["front_action", "back_action"]
    operation: str | None = None
    resource: str | None = None
    label: str | None = None
    triggers: str | None = None
    description: str | None = None
    user_tasks: list[str] = Field(default_factory=list)
    flows: list[str] = Field(default_factory=list)

    model_config = {"frozen": True}

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "type": self.type,
            "operation": self.operation,
            "resource": self.resource,
            "label": self.label,
            "triggers": self.triggers,
            "description": self.description,
            "user_tasks": self.user_tasks,
            "flows": self.flows,
        }


class Task(BaseModel):
    task: str
    type: str

    model_config = {"frozen": True}

    def to_dict(self) -> dict[str, str]:
        return {"task": self.task, "type": self.type}


class UserTask(BaseModel):
    user_task_id: str | None = None
    task: str
    type: str
    sequence: int | None = None
    name: str | None = None
    description: str | None = None
    front_actions: list[Action] = Field(default_factory=list)
    back_actions: list[Action] = Field(default_factory=list)

    model_config = {"frozen": True}

    def to_task(self) -> Task:
        return Task(task=self.task, type=self.type)

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_task_id": self.user_task_id,
            "task": self.task,
            "type": self.type,
            "sequence": self.sequence,
            "name": self.name,
            "description": self.description,
            "front_actions": [action.to_dict() for action in self.front_actions],
            "back_actions": [action.to_dict() for action in self.back_actions],
        }


class ProcessActor(BaseModel):
    actor_id: str
    name: str
    role: str
    type: Literal["customer", "employee", "team", "system", "external_party"]

    model_config = {"frozen": True}


class ProcessSystem(BaseModel):
    system_id: str
    name: str
    type: Literal["internal", "external", "manual", "api"]
    owner: str | None = None

    model_config = {"frozen": True}


class ProcessDocument(BaseModel):
    document_id: str
    name: str
    required: bool = True
    source: str | None = None

    model_config = {"frozen": True}


class ProcessRule(BaseModel):
    rule_id: str
    description: str
    severity: Literal["low", "medium", "high", "critical"] = "medium"
    source: str | None = None

    model_config = {"frozen": True}


class ProcessDecision(BaseModel):
    decision_id: str
    question: str
    outcomes: list[str] = Field(default_factory=list)

    model_config = {"frozen": True}


class ProcessException(BaseModel):
    exception_id: str
    condition: str
    resolution: str
    escalation: str | None = None

    model_config = {"frozen": True}


class ProcessIntegration(BaseModel):
    integration_id: str
    name: str
    type: Literal["legacy_service", "internal_service", "external_service", "mcp_tool", "manual"]
    protocol: Literal["api", "grpc", "mcp", "event", "database", "manual"]
    operation: str
    endpoint: str
    timeout_seconds: int = 30
    requires_approval: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"frozen": True}


class ProcessActivity(BaseModel):
    activity_id: str
    name: str
    type: Literal["use_case", "task", "service_call", "approval", "decision", "notification"]
    description: str
    owner: str | None = None
    step_ids: list[str] = Field(default_factory=list)
    execution_node_ids: list[str] = Field(default_factory=list)

    model_config = {"frozen": True}

    @model_validator(mode="before")
    @classmethod
    def _migrate_node_ids(cls, data: Any) -> Any:
        if isinstance(data, dict) and "node_ids" in data and "execution_node_ids" not in data:
            data = dict(data)
            data["execution_node_ids"] = data.pop("node_ids")
        return data


class ProcessExecutionNode(BaseModel):
    node_id: str
    step_id: str | None = None
    name: str
    type: Literal[
        "start",
        "wait_for_user_input",
        "state_update",
        "service_call",
        "decision",
        "approval",
        "notification",
        "end",
    ]
    implementation: str
    description: str
    required_inputs: list[str] = Field(default_factory=list)
    produced_outputs: list[str] = Field(default_factory=list)
    integration_id: str | None = None
    next_nodes: list[str] = Field(default_factory=list)
    on_success: str | None = None
    on_failure: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"frozen": True}


ProcessNode = ProcessExecutionNode


class ProcessTransition(BaseModel):
    from_node: str
    to_node: str
    condition: str = "always"
    description: str | None = None

    model_config = {"frozen": True}


class OrchestratorTimer(BaseModel):
    timer_id: str
    node_id: str
    delay_seconds: int | None = None
    due_at: datetime | None = None
    action: Literal["continue", "retry", "timeout", "escalate"]
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"frozen": True}


class OrchestratorAsyncContinuation(BaseModel):
    continuation_id: str
    node_id: str
    trigger: Literal["message", "timer", "job", "manual"]
    resume_node_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"frozen": True}


class OrchestratorEventListener(BaseModel):
    listener_id: str
    event: Literal[
        "process_started",
        "node_started",
        "node_completed",
        "node_failed",
        "process_waiting",
        "process_completed",
        "message_correlated",
        "compensation_started",
    ]
    implementation: str
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"frozen": True}


class OrchestratorCompensation(BaseModel):
    compensation_id: str
    node_id: str
    trigger: Literal["failure", "cancel", "timeout", "manual"]
    compensation_node_id: str | None = None
    integration_id: str | None = None
    description: str

    model_config = {"frozen": True}


class OrchestratorSubprocess(BaseModel):
    subprocess_id: str
    process_id: str
    start_node_id: str | None = None
    parent_node_id: str | None = None
    mode: Literal["embedded", "call_activity"] = "call_activity"
    input_mapping: dict[str, str] = Field(default_factory=dict)
    output_mapping: dict[str, str] = Field(default_factory=dict)

    model_config = {"frozen": True}


class OrchestratorMessageCorrelation(BaseModel):
    correlation_id: str
    message_name: str
    key: str
    target_node_id: str
    description: str | None = None

    model_config = {"frozen": True}


class OrchestratorJobDefinition(BaseModel):
    job_id: str
    node_id: str
    type: Literal["async_continuation", "timer", "message_wait", "retry", "compensation"]
    status: Literal["pending", "running", "completed", "failed", "cancelled"] = "pending"
    max_attempts: int = 1
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"frozen": True}


class ProcessStep(BaseModel):
    step_id: str
    sequence: int
    name: str
    type: Literal[
        "start",
        "user_task",
        "service_task",
        "decision",
        "approval",
        "notification",
        "end",
    ]
    actor_id: str | None = None
    system_id: str | None = None
    description: str
    required_documents: list[str] = Field(default_factory=list)
    rules: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    exceptions: list[str] = Field(default_factory=list)
    related_user_task_id: str | None = None
    executable: bool = False
    actions: list[str] = Field(default_factory=list)
    integrations: list[str] = Field(default_factory=list)
    execution_node_ids: list[str] = Field(default_factory=list)

    model_config = {"frozen": True}

    @model_validator(mode="before")
    @classmethod
    def _migrate_node_ids(cls, data: Any) -> Any:
        if isinstance(data, dict) and "node_ids" in data and "execution_node_ids" not in data:
            data = dict(data)
            data["execution_node_ids"] = data.pop("node_ids")
        return data


class ProcessDefinition(BaseModel):
    process_id: str
    process_name: str
    version: str = "1.0.0"
    status: Literal["draft", "approved", "deprecated"] = "draft"
    domain: str
    owner: str
    description: str
    related_flow_ids: list[str] = Field(default_factory=list)
    triggers: list[str] = Field(default_factory=list)
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    actors: list[ProcessActor] = Field(default_factory=list)
    systems: list[ProcessSystem] = Field(default_factory=list)
    documents: list[ProcessDocument] = Field(default_factory=list)
    rules: list[ProcessRule] = Field(default_factory=list)
    decisions: list[ProcessDecision] = Field(default_factory=list)
    exceptions: list[ProcessException] = Field(default_factory=list)
    integrations: list[ProcessIntegration] = Field(default_factory=list)
    activities: list[ProcessActivity] = Field(default_factory=list)
    execution_nodes: list[ProcessExecutionNode] = Field(default_factory=list)
    transitions: list[ProcessTransition] = Field(default_factory=list)
    timers: list[OrchestratorTimer] = Field(default_factory=list)
    async_continuations: list[OrchestratorAsyncContinuation] = Field(default_factory=list)
    event_listeners: list[OrchestratorEventListener] = Field(default_factory=list)
    compensations: list[OrchestratorCompensation] = Field(default_factory=list)
    subprocesses: list[OrchestratorSubprocess] = Field(default_factory=list)
    message_correlations: list[OrchestratorMessageCorrelation] = Field(default_factory=list)
    jobs: list[OrchestratorJobDefinition] = Field(default_factory=list)
    steps: list[ProcessStep] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"frozen": True}

    @model_validator(mode="before")
    @classmethod
    def _migrate_nodes(cls, data: Any) -> Any:
        if isinstance(data, dict) and "nodes" in data and "execution_nodes" not in data:
            data = dict(data)
            data["execution_nodes"] = data.pop("nodes")
        return data


class ProcessExecutionEvent(BaseModel):
    node_id: str
    status: Literal["completed", "waiting_for_user_input", "failed", "skipped"]
    message: str
    data: dict[str, Any] = Field(default_factory=dict)

    model_config = {"frozen": True}


class OrchestratorJob(BaseModel):
    job_id: str
    process_id: str
    instance_id: str
    node_id: str
    type: Literal["async_continuation", "timer", "message_wait", "retry", "compensation"]
    status: Literal["pending", "running", "completed", "failed", "cancelled"] = "pending"
    attempts: int = 0
    due_at: datetime | None = None
    payload: dict[str, Any] = Field(default_factory=dict)

    model_config = {"frozen": True}


class OrchestratorInstance(BaseModel):
    instance_id: str
    definition_type: Literal["flow", "process"]
    definition_id: str
    version: str | None = None
    status: Literal["running", "waiting", "completed", "failed", "cancelled", "compensating"] = "running"
    current_node_id: str | None = None
    parent_instance_id: str | None = None
    correlation_keys: dict[str, str] = Field(default_factory=dict)
    data: dict[str, Any] = Field(default_factory=dict)
    pending_jobs: list[OrchestratorJob] = Field(default_factory=list)
    events: list[ProcessExecutionEvent] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"frozen": True}


class ProcessExecutionResult(BaseModel):
    process_id: str
    instance_id: str | None = None
    status: Literal["completed", "waiting_for_user_input", "failed"]
    current_node_id: str | None = None
    waiting_for: list[str] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)
    events: list[ProcessExecutionEvent] = Field(default_factory=list)

    model_config = {"frozen": True}


class FlowDefinition(BaseModel):
    flow_id: str
    flow_name: str
    intent: str
    confidence: float
    business_event: str
    utterances: list[str]
    plan: list[str]
    tasks: list[Task]
    user_tasks: list[UserTask] = Field(default_factory=list)
    capabilities: list[str]
    concepts: list[str]
    concept_aliases: dict[str, list[str]] = Field(default_factory=dict)
    explanation: str
    source: str
    metadata: dict[str, Any] = {}

    model_config = {"frozen": True}


KnowledgeRecord = FlowDefinition


class AnswerResult(BaseModel):
    flow_id: str = "unknown"
    flow_name: str = "Unknown flow"
    intent: str
    confidence: float
    business_event: str
    requires_human_approval: bool
    plan: list[str]
    tasks: list[Task]
    related_capabilities: list[str]
    related_concepts: list[str]
    explanation: str
    clarification_options: list[dict[str, Any]] = Field(default_factory=list)

    model_config = {"frozen": True}

    def to_dict(self) -> dict[str, Any]:
        return {
            "can_resolve": self.intent != "unknown",
            "flow_id": self.flow_id,
            "flow_name": self.flow_name,
            "intent": self.intent,
            "confidence": self.confidence,
            "business_event": self.business_event,
            "requires_human_approval": self.requires_human_approval,
            "plan": self.plan,
            "tasks": [task.to_dict() for task in self.tasks],
            "related_capabilities": self.related_capabilities,
            "related_concepts": self.related_concepts,
            "explanation": self.explanation,
            "clarification_options": self.clarification_options,
        }
