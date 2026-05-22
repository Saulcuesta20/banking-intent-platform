from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


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


class KnowledgeRecord(BaseModel):
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
    ontology_nodes: list[str]
    ontology_aliases: dict[str, list[str]] = Field(default_factory=dict)
    explanation: str
    source: str
    metadata: dict[str, Any] = {}

    model_config = {"frozen": True}


class IntentResult(BaseModel):
    flow_id: str = "unknown"
    flow_name: str = "Unknown flow"
    intent: str
    confidence: float
    business_event: str
    requires_human_approval: bool
    plan: list[str]
    tasks: list[Task]
    related_capabilities: list[str]
    related_ontology_nodes: list[str]
    explanation: str

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
            "related_ontology_nodes": self.related_ontology_nodes,
            "explanation": self.explanation,
        }
