from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from importlib import import_module
from pathlib import Path
from typing import Any, Literal, TypedDict

from app.agents.skills.loader import SkillCatalogLoader
from app.agents.skills.models import AgentSkill
from app.config.settings import load_settings
from app.agents.models import AgentDefinition, AgentRunResult


class AgentEngineState(TypedDict, total=False):
    input: Any
    trace_events: list[dict[str, Any]]
    requested_tool_ids: list[str]
    denied_tool_ids: list[str]
    loaded_skills: list[dict[str, Any]]
    decision: str
    status: Literal["ok", "failed"]
    output: dict[str, Any]
    error: str


@dataclass(frozen=True)
class AgentEngine:
    """Execute declarative agent definitions with a LangGraph workflow."""

    skill_loader: SkillCatalogLoader = field(default_factory=SkillCatalogLoader)
    skill_catalog_path: Path = field(default_factory=lambda: load_settings().agent_skills_path)

    def run(self, definition: AgentDefinition, input_data: Any) -> AgentRunResult:
        try:
            graph = self._build_graph(definition)
            final_state = graph.invoke(
                {
                    "input": input_data,
                    "trace_events": [],
                    "status": "ok",
                }
            )
        except Exception as exc:
            return AgentRunResult(agent_id=definition.agent_id, status="failed", error=str(exc), trace=[])

        status = str(final_state.get("status") or "ok")
        trace_events = list(final_state.get("trace_events") or [])
        if status != "ok":
            return AgentRunResult(
                agent_id=definition.agent_id,
                status="failed",
                error=str(final_state.get("error") or "agent execution failed"),
                trace=trace_events,
            )

        return AgentRunResult(
            agent_id=definition.agent_id,
            status="ok",
            output=final_state.get("output"),
            trace=trace_events,
        )

    def _build_graph(self, definition: AgentDefinition):
        graph_module = self._optional_import("langgraph.graph", "langgraph")
        StateGraph = graph_module.StateGraph
        START = graph_module.START
        END = graph_module.END

        builder = StateGraph(AgentEngineState)
        builder.add_node("initialize", lambda state: self._initialize(definition, state))
        builder.add_node("load_skills", lambda state: self._load_skills(definition, state))
        builder.add_node("validate_policy", lambda state: self._validate_policy(definition, state))
        builder.add_node("route_class", lambda state: self._route_class(definition, state))
        builder.add_node("finalize", lambda state: self._finalize(definition, state))
        builder.add_edge(START, "initialize")
        builder.add_edge("initialize", "load_skills")
        builder.add_edge("load_skills", "validate_policy")
        builder.add_conditional_edges(
            "validate_policy",
            self._route_after_validation,
            {
                "blocked": "finalize",
                "continue": "route_class",
            },
        )
        builder.add_edge("route_class", "finalize")
        builder.add_edge("finalize", END)
        return builder.compile()

    def _initialize(self, definition: AgentDefinition, state: AgentEngineState) -> AgentEngineState:
        trace_events = list(state.get("trace_events") or [])
        trace_events.append(
            {
                "node": "initialize",
                "agent_id": definition.agent_id,
                "agent_class": definition.agent_class,
                "kind": definition.kind,
                "domain": definition.domain,
                "skills": list(definition.skills),
            }
        )
        requested_tool_ids = self._requested_tool_ids(state.get("input"))
        return {
            "trace_events": trace_events,
            "requested_tool_ids": requested_tool_ids,
        }

    def _load_skills(self, definition: AgentDefinition, state: AgentEngineState) -> AgentEngineState:
        trace_events = list(state.get("trace_events") or [])
        available_skills = self.skill_loader.load_index(self.skill_catalog_path)
        resolved_skills: list[AgentSkill] = []
        missing_skill_ids: list[str] = []
        for skill_id in definition.skill_ids:
            skill = available_skills.get(skill_id)
            if skill is None:
                missing_skill_ids.append(skill_id)
                continue
            resolved_skills.append(skill)
        trace_events.append(
            {
                "node": "load_skills",
                "skill_ids": list(definition.skill_ids),
                "loaded_skill_ids": [skill.skill_id for skill in resolved_skills],
                "missing_skill_ids": missing_skill_ids,
            }
        )
        return {
            "trace_events": trace_events,
            "loaded_skills": [
                {
                    "skill_id": skill.skill_id,
                    "name": skill.name,
                    "description": skill.description,
                    "allowed_tools": list(skill.allowed_tools),
                    "disable_model_invocation": skill.disable_model_invocation,
                    "preview": skill.preview(),
                }
                for skill in resolved_skills
            ],
            "status": "ok" if not missing_skill_ids else "failed",
            "error": None if not missing_skill_ids else f"Missing skills: {', '.join(missing_skill_ids)}",
        }

    def _validate_policy(self, definition: AgentDefinition, state: AgentEngineState) -> AgentEngineState:
        trace_events = list(state.get("trace_events") or [])
        if state.get("status") == "failed":
            trace_events.append(
                {
                    "node": "validate_policy",
                    "status": "skipped",
                    "reason": "prior_failure",
                }
            )
            return {
                "trace_events": trace_events,
                "status": "failed",
                "error": str(state.get("error") or "agent execution failed"),
            }
        requested_tool_ids = list(state.get("requested_tool_ids") or [])
        allowed_tool_ids = list(definition.tool_ids or definition.policy.allowed_tool_ids)
        denied_tool_ids = [tool_id for tool_id in requested_tool_ids if tool_id not in allowed_tool_ids]
        trace_events.append(
            {
                "node": "validate_policy",
                "requested_tool_ids": requested_tool_ids,
                "allowed_tool_ids": allowed_tool_ids,
                "denied_tool_ids": denied_tool_ids,
            }
        )
        if denied_tool_ids:
            return {
                "trace_events": trace_events,
                "denied_tool_ids": denied_tool_ids,
                "status": "failed",
                "error": f"Agent is not allowed to use tool_ids: {', '.join(denied_tool_ids)}",
            }
        return {
            "trace_events": trace_events,
            "denied_tool_ids": [],
            "status": "ok",
        }

    def _route_after_validation(self, state: AgentEngineState) -> str:
        return "blocked" if state.get("status") == "failed" else "continue"

    def _route_class(self, definition: AgentDefinition, state: AgentEngineState) -> AgentEngineState:
        trace_events = list(state.get("trace_events") or [])
        route = {
            "planning": "plan",
            "coordinator": "coordinate",
            "delegator": "delegate",
            "worker": "assist",
            "monitoring": "monitor",
        }.get(definition.agent_class, "assist")
        trace_events.append(
            {
                "node": "route_class",
                "agent_class": definition.agent_class,
                "route": route,
            }
        )
        return {
            "trace_events": trace_events,
            "decision": route,
            "status": "ok",
        }

    def _finalize(self, definition: AgentDefinition, state: AgentEngineState) -> AgentEngineState:
        trace_events = list(state.get("trace_events") or [])
        if state.get("status") == "failed":
            trace_events.append(
                {
                    "node": "finalize",
                    "status": "failed",
                    "error": state.get("error"),
                }
            )
            return {
                "trace_events": trace_events,
                "status": "failed",
                "error": str(state.get("error") or "agent execution failed"),
            }

        output = {
            "agent_id": definition.agent_id,
            "agent_class": definition.agent_class,
            "kind": definition.kind,
            "domain": definition.domain,
            "goals": list(definition.goals),
            "skills": list(definition.skills),
            "skill_ids": list(definition.skill_ids),
            "tool_ids": list(definition.tool_ids),
            "loaded_skills": list(state.get("loaded_skills") or []),
            "decision": state.get("decision") or "assist",
            "input": state.get("input"),
            "policy": {
                "max_retries": definition.policy.max_retries,
                "requires_human_review": definition.policy.requires_human_review,
                "allowed_tool_ids": list(definition.policy.allowed_tool_ids),
            },
        }
        trace_events.append(
            {
                "node": "finalize",
                "status": "ok",
                "decision": output["decision"],
            }
        )
        return {
            "trace_events": trace_events,
            "output": output,
            "status": "ok",
        }

    def _requested_tool_ids(self, input_data: Any) -> list[str]:
        if isinstance(input_data, dict):
            requested = input_data.get("tool_ids") or input_data.get("requested_tool_ids") or []
            return [str(tool_id) for tool_id in requested if str(tool_id)]
        return []

    def _optional_import(self, module_name: str, package_name: str):
        try:
            return import_module(module_name)
        except Exception:
            class _FallbackGraphModule:
                START = "__start__"
                END = "__end__"

                class StateGraph:
                    def __init__(self, _state_schema):
                        self.nodes: dict[str, Any] = {}
                        self.edges: list[tuple[str, str]] = []
                        self.conditional_edges: list[tuple[str, Any, dict[str, str]]] = []

                    def add_node(self, name: str, func: Any) -> None:
                        self.nodes[name] = func

                    def add_edge(self, source: str, target: str) -> None:
                        self.edges.append((source, target))

                    def add_conditional_edges(self, source: str, router: Any, path_map: dict[str, str]) -> None:
                        self.conditional_edges.append((source, router, path_map))

                    def compile(self):
                        graph = self

                        class _App:
                            def invoke(self, state: dict[str, Any]) -> dict[str, Any]:
                                current_state = dict(state)
                                current = "initialize"
                                while current:
                                    current_state.update(graph.nodes[current](current_state))
                                    if current == "validate_policy":
                                        _, router, path_map = graph.conditional_edges[0]
                                        branch = router(current_state)
                                        current = path_map[branch]
                                        if current == "finalize":
                                            continue
                                    if current == "initialize":
                                        current = "validate_policy"
                                    elif current == "route_class":
                                        current = "finalize"
                                    elif current == "finalize":
                                        break
                                return current_state

                        return _App()

            return _FallbackGraphModule()
