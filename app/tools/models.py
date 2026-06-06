from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


ToolType = Literal["frontend_tool", "backend_tool", "llm_tool"]
BackendProtocol = Literal["http", "grpc", "mcp", "database"]
LLMOperation = Literal["chat_completion", "json_completion", "embedding", "tool_call"]


class ToolDefinition(BaseModel):
    """Canonical invocable tool definition.

    Protocol is intentionally scoped to backend tools. Frontend and LLM tools
    use their own invocation-specific fields instead of pretending those are
    network protocols.
    """

    tool_id: str
    tool_type: ToolType
    operation: str | None = None
    resource: str | None = None
    label: str | None = None
    description: str | None = None
    triggers: str | None = None
    frontend_event: str | None = None
    backend_protocol: BackendProtocol | None = None
    endpoint: str | None = None
    llm_operation: LLMOperation | None = None
    llm_model: str | None = None
    llm_provider: str | None = None
    requires_approval: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"frozen": True}

    @model_validator(mode="after")
    def _validate_invocation_shape(self) -> "ToolDefinition":
        if self.tool_type != "backend_tool" and self.backend_protocol is not None:
            raise ValueError("backend_protocol is only valid for backend_tool.")
        if self.tool_type != "llm_tool" and (self.llm_operation is not None or self.llm_model is not None):
            raise ValueError("llm_operation and llm_model are only valid for llm_tool.")
        if self.tool_type != "frontend_tool" and self.frontend_event is not None:
            raise ValueError("frontend_event is only valid for frontend_tool.")
        return self

    @classmethod
    def from_legacy_action(
        cls,
        action: Any,
        *,
        user_tasks: list[str] | None = None,
        flows: list[str] | None = None,
    ) -> "ToolRegistryEntry":
        action_id = str(
            getattr(action, "action_id", None)
            or getattr(action, "action", None)
            or getattr(action, "tool_id", "")
        )
        legacy_type = str(getattr(action, "type", ""))
        tool_type: ToolType = "frontend_tool" if legacy_type in {"front_action", "front"} else "backend_tool"
        return ToolRegistryEntry(
            tool_id=action_id,
            tool_type=tool_type,
            operation=getattr(action, "operation", None),
            resource=getattr(action, "resource", None),
            label=getattr(action, "label", None),
            description=getattr(action, "description", None),
            triggers=getattr(action, "triggers", None),
            frontend_event=getattr(action, "triggers", None) if tool_type == "frontend_tool" else None,
            user_tasks=sorted(user_tasks or []),
            flows=sorted(flows or []),
        )

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class ToolRegistryEntry(ToolDefinition):
    user_tasks: list[str] = Field(default_factory=list)
    flows: list[str] = Field(default_factory=list)

    def to_legacy_action_dict(self) -> dict[str, Any]:
        legacy_type = "front" if self.tool_type == "frontend_tool" else "back"
        return {
            "action": self.tool_id,
            "action_id": self.tool_id,
            "type": legacy_type,
            "implementation_type": "show_form" if self.tool_type == "frontend_tool" else ("llm_tool" if self.tool_type == "llm_tool" else "tool_call"),
            "tool_id": self.tool_id if self.tool_type != "frontend_tool" else None,
            "operation": self.operation,
            "resource": self.resource,
            "label": self.label,
            "triggers": self.triggers,
            "description": self.description,
            "user_tasks": self.user_tasks,
            "flows": self.flows,
        }
