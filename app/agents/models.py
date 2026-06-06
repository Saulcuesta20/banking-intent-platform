from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


AgentKind = Literal["coordinator", "delegator", "worker"]
AgentDomain = Literal["ingestion", "ask", "asset", "tool", "system"]


class AgentPolicy(BaseModel):
    """Runtime guardrails for an agent."""

    max_retries: int = 0
    requires_human_review: bool = False
    allowed_tool_ids: list[str] = Field(default_factory=list)

    model_config = {"frozen": True}


class AgentDefinition(BaseModel):
    """Platform-owned agent contract layered above LangGraph."""

    agent_id: str
    name: str
    role: str
    kind: AgentKind
    domain: AgentDomain
    goals: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    graph_name: str | None = None
    state_schema: str | None = None
    policy: AgentPolicy = Field(default_factory=AgentPolicy)

    model_config = {"frozen": True}


class AgentRunResult(BaseModel):
    """Auditable result envelope returned by every agent."""

    agent_id: str
    status: Literal["ok", "failed", "unsupported"] = "ok"
    output: Any = None
    trace: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None

    model_config = {"arbitrary_types_allowed": True}

