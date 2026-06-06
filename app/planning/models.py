from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


KnownTargetType = Literal["flow", "process", "qa", "tool", "business_rule", "plan", "concept", "document"]
NeedKind = Literal["execution", "question", "explanation", "clarification", "unsupported"]
ResolutionAction = Literal[
    "answer_question",
    "explain_tool",
    "invoke_known_flow",
    "invoke_known_process",
    "compose_multiple_intentions_plan",
    "ask_clarification",
    "reject_unsupported",
    "escalate_to_human",
]
RouteMode = Literal["known_route", "multiple_intentions", "clarification", "unsupported"]


class Goal(BaseModel):
    summary: str
    type: Literal["business_goal", "knowledge_goal", "operational_goal", "unknown"] = "unknown"
    confidence: float = 0.0

    model_config = {"frozen": True}


class KnownTarget(BaseModel):
    type: KnownTargetType
    id: str
    label: str | None = None
    confidence: float = 0.0

    model_config = {"frozen": True}


class UserNeed(BaseModel):
    need_id: str
    kind: NeedKind
    text: str
    resolution_action: ResolutionAction
    known_targets: list[KnownTarget] = Field(default_factory=list)
    reason: str = ""

    model_config = {"frozen": True}


class RouteDecision(BaseModel):
    mode: RouteMode
    reason: str
    primary_target: KnownTarget | None = None
    targets: list[KnownTarget] = Field(default_factory=list)
    requires_clarification: bool = False
    clarification_question: str | None = None

    model_config = {"frozen": True}


class MultipleIntentionsPlanStep(BaseModel):
    step: str
    type: str
    source_need_ids: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    condition: str | None = None
    reason: str = ""

    model_config = {"frozen": True}

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy_actions(cls, data: Any) -> Any:
        if isinstance(data, dict) and "actions" in data and "tools" not in data:
            data = dict(data)
            data["tools"] = data["actions"]
        return data

    @property
    def actions(self) -> list[str]:
        """Deprecated compatibility alias for older callers."""
        return self.tools


class MultipleIntentionsPlan(BaseModel):
    planning_mode: Literal["none", "known_route_projection", "multiple_intentions"] = "none"
    selected_targets: list[KnownTarget] = Field(default_factory=list)
    steps: list[MultipleIntentionsPlanStep] = Field(default_factory=list)
    missing_capabilities: list[str] = Field(default_factory=list)
    validation_errors: list[str] = Field(default_factory=list)

    model_config = {"frozen": True}


class PlanningTrace(BaseModel):
    """Complete planning output used by ask routing and response projection."""

    goal: Goal
    user_needs: list[UserNeed] = Field(default_factory=list)
    route: RouteDecision
    multiple_intentions_plan: MultipleIntentionsPlan = Field(default_factory=MultipleIntentionsPlan)

    model_config = {"frozen": True}

    def to_dict(self) -> dict[str, Any]:
        """Serialize the trace for API responses and audit payloads."""
        return self.model_dump(mode="json")
