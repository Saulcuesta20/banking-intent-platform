from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from pydantic import BaseModel, Field, model_validator

from app.tools.models import ToolDefinition


def _normalize_identifier(value: str) -> str:
    normalized = "".join(char.lower() if char.isalnum() else "_" for char in value.strip())
    while "__" in normalized:
        normalized = normalized.replace("__", "_")
    return normalized.strip("_")


def _normalize_implementation_type(
    value: Any,
    *,
    type_hint: str | None = None,
    tool_id: str | None = None,
) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"show_form", "open_panel", "submit_search", "tool_call", "llm_tool", "service_call", "custom"}:
        return normalized
    if normalized in {"service_invocation", "service", "service_action"}:
        return "service_call"
    if normalized in {"ui", "front", "frontend", "front_action", "open_ui", "show_ui"}:
        return "show_form" if normalized != "open_ui" else "open_panel"
    if normalized in {"panel", "open_panel_view"}:
        return "open_panel"
    if normalized in {"search", "submit"}:
        return "submit_search"
    if normalized in {"tool", "backend", "backend_tool"}:
        return "tool_call"
    if normalized == "llm":
        return "llm_tool"
    if type_hint == "front":
        return "show_form" if normalized else "custom"
    if type_hint == "back":
        normalized_tool_id = str(tool_id or "")
        return "llm_tool" if "llm" in normalized_tool_id else "tool_call"
    return "custom"


class Action(BaseModel):
    action_id: str
    type: Literal["front", "back"]
    implementation_type: Literal["show_form", "open_panel", "submit_search", "tool_call", "llm_tool", "service_call", "custom"] = "custom"
    lifecycle_state: Literal["not_started", "on_user_enter", "cancelled", "completed"] = "not_started"
    tool_id: str | None = None
    tool_ids: list[str] = Field(default_factory=list)
    label: str | None = None
    triggers: str | None = None
    description: str | None = None

    model_config = {"frozen": True}

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy_action_shape(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        data = dict(data)
        if "tool_id" not in data and "tool" in data:
            data["tool_id"] = data["tool"]
        if "action_id" not in data and "action" in data:
            data["action_id"] = data["action"]
        if "action_id" not in data and data.get("tool_id"):
            data["action_id"] = data["tool_id"]
        action_type = str(data.get("type") or "").strip()
        if action_type == "front_action":
            data["type"] = "front"
        elif action_type == "back_action":
            data["type"] = "back"
        if not data.get("tool_id") and str(data.get("type") or "") == "back":
            data["tool_id"] = data.get("action_id")
        if "tool_ids" not in data or not data.get("tool_ids"):
            if isinstance(data.get("tool_id"), str) and data["tool_id"].strip():
                data["tool_ids"] = [data["tool_id"].strip()]
            else:
                data["tool_ids"] = []
        data["implementation_type"] = _normalize_implementation_type(
            data.get("implementation_type"),
            type_hint=str(data.get("type") or "").strip(),
            tool_id=str(data.get("tool_id") or data.get("action_id") or ""),
        )
        lifecycle_state = str(data.get("lifecycle_state") or "").strip().lower().replace("-", "_")
        data["lifecycle_state"] = lifecycle_state if lifecycle_state in {"not_started", "on_user_enter", "cancelled", "completed"} else "not_started"
        return data

    @property
    def action(self) -> str:
        """Legacy compatibility alias."""
        return self.action_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action_id,
            "type": self.type,
            "implementation_type": self.implementation_type,
            "lifecycle_state": self.lifecycle_state,
            "tool": self.tool_id,
            "tool_ids": list(self.tool_ids),
            "label": self.label,
            "triggers": self.triggers,
            "description": self.description,
        }


class ActionRegistryEntry(BaseModel):
    action_id: str
    type: Literal["front", "back"]
    implementation_type: Literal["show_form", "open_panel", "submit_search", "tool_call", "llm_tool", "service_call", "custom"] = "custom"
    lifecycle_state: Literal["not_started", "on_user_enter", "cancelled", "completed"] = "not_started"
    tool_id: str | None = None
    tool_ids: list[str] = Field(default_factory=list)
    label: str | None = None
    triggers: str | None = None
    description: str | None = None
    user_tasks: list[str] = Field(default_factory=list)
    flows: list[str] = Field(default_factory=list)

    model_config = {"frozen": True}

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy_action_registry_shape(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        data = dict(data)
        if "tool_id" not in data and "tool" in data:
            data["tool_id"] = data["tool"]
        if "action_id" not in data and "action" in data:
            data["action_id"] = data["action"]
        if "action_id" not in data and data.get("tool_id"):
            data["action_id"] = data["tool_id"]
        action_type = str(data.get("type") or "").strip()
        if action_type == "front_action":
            data["type"] = "front"
        elif action_type == "back_action":
            data["type"] = "back"
        if not data.get("tool_id") and str(data.get("type") or "") == "back":
            data["tool_id"] = data.get("action_id")
        if "tool_ids" not in data or not data.get("tool_ids"):
            if isinstance(data.get("tool_id"), str) and data["tool_id"].strip():
                data["tool_ids"] = [data["tool_id"].strip()]
            else:
                data["tool_ids"] = []
        data["implementation_type"] = _normalize_implementation_type(
            data.get("implementation_type"),
            type_hint=str(data.get("type") or "").strip(),
            tool_id=str(data.get("tool_id") or data.get("action_id") or ""),
        )
        lifecycle_state = str(data.get("lifecycle_state") or "").strip().lower().replace("-", "_")
        data["lifecycle_state"] = lifecycle_state if lifecycle_state in {"not_started", "on_user_enter", "cancelled", "completed"} else "not_started"
        return data

    @property
    def action(self) -> str:
        """Legacy compatibility alias."""
        return self.action_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action_id,
            "type": self.type,
            "implementation_type": self.implementation_type,
            "lifecycle_state": self.lifecycle_state,
            "tool": self.tool_id,
            "tool_ids": list(self.tool_ids),
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
    name: str | None = None
    description: str | None = None
    tools: list[ToolDefinition] = Field(default_factory=list)
    user_actions: list[Action] = Field(default_factory=list)

    model_config = {"frozen": True}

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy_actions_to_tools(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        data = dict(data)
        tools = list(data.get("tools") or [])
        if not tools:
            tools.extend(cls._tools_from_legacy_actions(data.get("front_actions") or [], "frontend_tool"))
            tools.extend(cls._tools_from_legacy_actions(data.get("back_actions") or [], "backend_tool"))
            data["tools"] = tools
        if not data.get("front_actions") or not data.get("back_actions"):
            front_actions, back_actions = cls._legacy_actions_from_tools(tools)
            if not data.get("front_actions"):
                data["front_actions"] = front_actions
            if not data.get("back_actions"):
                data["back_actions"] = back_actions
        if not data.get("user_actions"):
            data["user_actions"] = cls._user_actions_from_legacy_shapes(
                data.get("front_actions") or [],
                data.get("back_actions") or [],
                tools,
            )
        data.pop("interaction_steps", None)
        data.pop("sequence", None)
        return data

    def to_task(self) -> Task:
        return Task(task=self.task, type=self.type)

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_task_id": self.user_task_id,
            "task": self.task,
            "type": self.type,
            "name": self.name,
            "description": self.description,
            "user_actions": [action.to_dict() for action in self.user_actions],
            "tools": [tool.to_dict() for tool in self.tools],
        }

    @staticmethod
    def _tools_from_legacy_actions(actions: list[Any], tool_type: str) -> list[dict[str, Any]]:
        tools = []
        for action in actions:
            if isinstance(action, dict):
                action_data = action
            else:
                action_data = action.model_dump(mode="json") if hasattr(action, "model_dump") else {}
            if not action_data:
                continue
            tool = {
                "tool_id": action_data.get("action") or action_data.get("tool_id"),
                "tool_type": tool_type,
                "operation": action_data.get("operation"),
                "resource": action_data.get("resource"),
                "label": action_data.get("label"),
                "description": action_data.get("description"),
                "triggers": action_data.get("triggers"),
            }
            if tool_type == "frontend_tool":
                tool["frontend_event"] = action_data.get("triggers")
            tools.append({key: value for key, value in tool.items() if value is not None})
        return tools

    @staticmethod
    def _legacy_actions_from_tools(tools: list[Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        front_actions = []
        back_actions = []
        for raw_tool in tools:
            tool = raw_tool if isinstance(raw_tool, dict) else raw_tool.model_dump(mode="json")
            tool_type = tool.get("tool_type")
            if tool_type not in {"frontend_tool", "backend_tool"}:
                continue
            legacy = {
                "action": tool.get("tool_id"),
                "type": "front" if tool_type == "frontend_tool" else "back",
                "tool_id": tool.get("tool_id"),
                "implementation_type": "show_form" if tool_type == "frontend_tool" else ("llm_tool" if "llm" in str(tool.get("tool_id") or "") else "tool_call"),
                "operation": tool.get("operation"),
                "resource": tool.get("resource"),
                "label": tool.get("label"),
                "triggers": tool.get("triggers") or tool.get("frontend_event"),
                "description": tool.get("description"),
            }
            legacy = {key: value for key, value in legacy.items() if value is not None}
            if tool_type == "frontend_tool":
                front_actions.append(legacy)
            else:
                back_actions.append(legacy)
        return front_actions, back_actions

    @staticmethod
    def _user_actions_from_legacy_shapes(
        front_actions: list[Any],
        back_actions: list[Any],
        tools: list[Any],
    ) -> list[dict[str, Any]]:
        user_actions: list[dict[str, Any]] = []
        for action in front_actions:
            payload = action if isinstance(action, dict) else action.model_dump(mode="json")
            if not payload:
                continue
                user_actions.append(
                    {
                        "action_id": payload.get("action_id") or payload.get("action"),
                        "type": "front",
                        "implementation_type": payload.get("implementation_type") or ("show_form" if payload.get("triggers") else "custom"),
                        "lifecycle_state": payload.get("lifecycle_state") or "not_started",
                        "tool_id": payload.get("tool_id"),
                        "tool_ids": [payload["tool_id"]] if payload.get("tool_id") else [],
                        "label": payload.get("label"),
                    "triggers": payload.get("triggers"),
                    "description": payload.get("description"),
                }
            )
        if back_actions:
            for action in back_actions:
                payload = action if isinstance(action, dict) else action.model_dump(mode="json")
                if not payload:
                    continue
                tool_id = payload.get("tool_id") or payload.get("action_id") or payload.get("action")
                user_actions.append(
                    {
                        "action_id": payload.get("action_id") or payload.get("action"),
                        "type": "back",
                        "implementation_type": payload.get("implementation_type") or ("llm_tool" if "llm" in str(tool_id or "") else "tool_call"),
                        "lifecycle_state": payload.get("lifecycle_state") or "not_started",
                        "tool_id": tool_id,
                        "tool_ids": [tool_id] if tool_id else [],
                        "label": payload.get("label"),
                        "triggers": payload.get("triggers"),
                        "description": payload.get("description"),
                    }
                )
        elif tools:
            for raw_tool in tools:
                tool = raw_tool if isinstance(raw_tool, dict) else raw_tool.model_dump(mode="json")
                tool_id = tool.get("tool_id")
                if not tool_id:
                    continue
                tool_type = str(tool.get("tool_type") or "")
                user_actions.append(
                    {
                        "action_id": tool_id,
                        "type": "front" if tool_type == "frontend_tool" else "back",
                        "implementation_type": "show_form" if tool_type == "frontend_tool" else ("llm_tool" if "llm" in str(tool_id) else "tool_call"),
                        "lifecycle_state": "not_started",
                        "tool_id": tool_id,
                        "tool_ids": [tool_id],
                        "label": tool.get("label"),
                        "triggers": tool.get("triggers") or tool.get("frontend_event"),
                        "description": tool.get("description"),
                    }
                )
        return user_actions


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
    tool_id: str | None = None
    name: str
    type: Literal["legacy_service", "internal_service", "external_service", "mcp_tool", "manual"]
    protocol: Literal["api", "grpc", "mcp", "event", "database", "manual"]
    operation: str
    endpoint: str
    timeout_seconds: int = 30
    requires_approval: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"frozen": True}

    @model_validator(mode="before")
    @classmethod
    def _default_tool_id(cls, data: Any) -> Any:
        if isinstance(data, dict) and "tool_id" not in data:
            data = dict(data)
            data["tool_id"] = data.get("endpoint") or data.get("integration_id")
        return data


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
        "user_task",
        "agent",
        "wait_for_user_input",
        "state_update",
        "service_call",
        "tool_call",
        "subprocess_call",
        "decision",
        "approval",
        "notification",
        "end",
    ]
    node_kind: Literal["system", "user_task", "agent", "custom"] = "system"
    wait_state: bool = False
    implementation: str
    description: str
    required_inputs: list[str] = Field(default_factory=list)
    produced_outputs: list[str] = Field(default_factory=list)
    related_user_task_id: str | None = None
    user_actions: list[Action] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    integration_id: str | None = None
    next_nodes: list[str] = Field(default_factory=list)
    on_success: str | None = None
    on_failure: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"frozen": True}

    @model_validator(mode="before")
    @classmethod
    def _migrate_node_action_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        data = dict(data)
        node_name = str(data.get("name") or "").strip()
        node_type = str(data.get("type") or "").strip()
        if "node_id" not in data or not data.get("node_id"):
            if node_type in {"start", "end"}:
                data["node_id"] = node_type
            elif node_name:
                data["node_id"] = _normalize_identifier(node_name)
        if "action_ids" in data and "actions" not in data:
            data["actions"] = data.pop("action_ids")
        if "capabilities" in data and "tools" not in data:
            data["tools"] = data.pop("capabilities")
        if "step_id" in data and "related_user_task_id" not in data:
            # Maintain backward compatibility while moving to user-task-oriented nodes.
            data["related_user_task_id"] = data["step_id"]
        if "node_kind" not in data or not data.get("node_kind"):
            if node_type == "user_task":
                data["node_kind"] = "user_task"
            elif node_type == "agent":
                data["node_kind"] = "agent"
            else:
                data["node_kind"] = "system"
        if data.get("type") == "user_task" and "wait_state" not in data:
            data["wait_state"] = True
        if data.get("type") == "user_task" and "related_user_task_id" not in data and node_name:
            data["related_user_task_id"] = _normalize_identifier(node_name)
        if "user_actions" not in data or not data.get("user_actions"):
            user_actions: list[dict[str, Any]] = []
            for action_id in data.get("actions") or []:
                user_actions.append(
                    {
                        "action_id": action_id,
                        "type": "front",
                        "implementation_type": "custom",
                    }
                )
            for tool_id in data.get("tools") or []:
                user_actions.append(
                    {
                        "action_id": tool_id,
                        "type": "back",
                        "tool_id": tool_id,
                        "implementation_type": "llm_tool" if "llm" in str(tool_id) else "tool_call",
                    }
                )
            if user_actions:
                data["user_actions"] = user_actions
        return data


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
    tools: list[str] = Field(default_factory=list)
    integrations: list[str] = Field(default_factory=list)
    execution_node_ids: list[str] = Field(default_factory=list)

    model_config = {"frozen": True}

    @model_validator(mode="before")
    @classmethod
    def _migrate_node_ids(cls, data: Any) -> Any:
        if isinstance(data, dict) and "node_ids" in data and "execution_node_ids" not in data:
            data = dict(data)
            data["execution_node_ids"] = data.pop("node_ids")
        if isinstance(data, dict) and "actions" in data and "tools" not in data:
            data = dict(data)
            data["tools"] = data["actions"]
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
    # Legacy only: execution_nodes is the canonical execution graph.
    steps: list[ProcessStep] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"frozen": True}

    @model_validator(mode="before")
    @classmethod
    def _migrate_nodes(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data = dict(data)
            if "nodes" in data and "execution_nodes" not in data and "user_flow" not in data:
                data["execution_nodes"] = data.pop("nodes")
            if "user_flow" in data and "execution_nodes" not in data:
                data["execution_nodes"] = data.pop("user_flow")
            if not data.get("transitions") and data.get("execution_nodes"):
                node_refs: list[str] = []
                for raw_node in data.get("execution_nodes") or []:
                    if not isinstance(raw_node, dict):
                        continue
                    node_type = str(raw_node.get("type") or "").strip()
                    node_id = str(raw_node.get("node_id") or "").strip()
                    node_name = str(raw_node.get("name") or "").strip()
                    if node_id:
                        node_refs.append(node_id)
                    elif node_type in {"start", "end"}:
                        node_refs.append(node_type)
                    elif node_name:
                        node_refs.append(_normalize_identifier(node_name))
                if len(node_refs) > 1:
                    data["transitions"] = [
                        {"from_node": node_refs[index], "to_node": node_refs[index + 1]}
                        for index in range(len(node_refs) - 1)
                    ]
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
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = {"frozen": True}


class ProcessExecutionResult(BaseModel):
    process_id: str
    instance_id: str | None = None
    status: Literal["completed", "waiting_for_user_input", "failed"]
    current_node_id: str | None = None
    waiting_for: list[str] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)
    events: list[ProcessExecutionEvent] = Field(default_factory=list)
    workflow_trace: list[dict[str, Any]] = Field(default_factory=list)

    model_config = {"frozen": True}


class FlowDefinition(BaseModel):
    flow_id: str
    flow_name: str
    intent: str
    confidence: float = 0.0
    business_event: str
    utterances: list[str] = Field(default_factory=list)
    plan: list[str] = Field(default_factory=list)
    tasks: list[Task]
    user_tasks: list[UserTask] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    concepts: list[str] = Field(default_factory=list)
    concept_aliases: dict[str, list[str]] = Field(default_factory=dict)
    explanation: str
    source: str
    metadata: dict[str, Any] = Field(default_factory=dict)

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
    goal: dict[str, Any] | None = None
    user_needs: list[dict[str, Any]] = Field(default_factory=list)
    route: dict[str, Any] | None = None
    multiple_intentions_plan: dict[str, Any] | None = None
    requires_execution_confirmation: bool = True
    execution_selection_policy: dict[str, Any] | None = None
    execution_options: list[dict[str, Any]] = Field(default_factory=list)

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
            "goal": self.goal,
            "user_needs": self.user_needs,
            "route": self.route,
            "multiple_intentions_plan": self.multiple_intentions_plan,
            "requires_execution_confirmation": self.requires_execution_confirmation,
            "execution_selection_policy": self.execution_selection_policy,
            "execution_options": self.execution_options,
        }
