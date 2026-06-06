from __future__ import annotations

from dataclasses import dataclass, field
from importlib import import_module
from typing import Any, Literal, NotRequired, TypedDict

from app.knowledge_base.models import EnterpriseAsset
from app.knowledge_base.repository import EnterpriseAssetRepository
from app.knowledge_base.service import KnowledgeBaseService
from app.models import (
    KnowledgeRecord,
    OrchestratorInstance,
    ProcessDefinition,
    ProcessExecutionNode,
    ProcessExecutionEvent,
    ProcessExecutionResult,
    ProcessIntegration,
)
from app.orchestrator.node_definition import NodeDefinitionModel
from app.orchestrator.service import OrchestratorService
from app.orchestrator.process_providers import IntegrationProviderRegistry


class OrchestrationExecutionError(RuntimeError):
    """Raised when a flow or process cannot be executed safely."""

    pass


class OrchestrationExecutionState(TypedDict, total=False):
    definition_type: Literal["flow", "process"]
    definition_id: str
    instance_id: str | None
    flow_id: str | None
    process_id: str | None
    process: ProcessDefinition
    flow: KnowledgeRecord | None
    current_node_id: str | None
    status: str
    waiting_for: list[str]
    data: dict[str, Any]
    events: list[ProcessExecutionEvent]
    workflow_trace: list[dict[str, Any]]
    error: NotRequired[str]
    rule_gates: NotRequired[list[dict[str, Any]]]


@dataclass(frozen=True)
class OrchestrationExecutionRequest:
    """Input command for starting or resuming a flow/process execution."""

    flow_id: str | None = None
    process_id: str | None = None
    instance_id: str | None = None
    data: dict[str, Any] | None = None
    resume_from_node_id: str | None = None
    use_langgraph: bool = True


@dataclass
class OrchestrationExecutorService:
    """Adapt confirmed flow/process execution into a workflow invocation.

    The orchestrator package owns process runtime state and invokes LangGraph
    when available. Node bodies stay deterministic and delegate protocol calls
    through provider adapters.
    """

    integration_registry: IntegrationProviderRegistry = field(default_factory=IntegrationProviderRegistry)
    orchestrator_service: OrchestratorService = field(default_factory=OrchestratorService)
    asset_repository: EnterpriseAssetRepository | None = None
    knowledge_base_service: KnowledgeBaseService | None = None
    node_definition_model: NodeDefinitionModel = field(default_factory=NodeDefinitionModel)

    def validate_loaded_definitions(self) -> dict[str, Any]:
        """Validate graph-loaded flow/process definitions against node policy."""
        process_results: list[dict[str, Any]] = []
        flow_results: list[dict[str, Any]] = []
        errors: list[str] = []
        for process in self._processes():
            try:
                self.node_definition_model.policy.validate("process", process.process_id, process.execution_nodes)
                process_results.append(
                    {
                        "definition_type": "process",
                        "definition_id": process.process_id,
                        "nodes": len(process.execution_nodes),
                        "status": "ok",
                    }
                )
            except Exception as exc:
                message = f"process.{process.process_id}: {exc}"
                errors.append(message)
                process_results.append(
                    {
                        "definition_type": "process",
                        "definition_id": process.process_id,
                        "nodes": len(process.execution_nodes),
                        "status": "invalid",
                        "error": str(exc),
                    }
                )

        for flow_id, process in self._flow_processes().items():
            try:
                self.node_definition_model.policy.validate("flow", flow_id, process.execution_nodes)
                flow_results.append(
                    {
                        "definition_type": "flow",
                        "definition_id": flow_id,
                        "nodes": len(process.execution_nodes),
                        "status": "ok",
                    }
                )
            except Exception as exc:
                message = f"flow.{flow_id}: {exc}"
                errors.append(message)
                flow_results.append(
                    {
                        "definition_type": "flow",
                        "definition_id": flow_id,
                        "nodes": len(process.execution_nodes),
                        "status": "invalid",
                        "error": str(exc),
                    }
                )

        return {
            "enabled": True,
            "process_definitions": process_results,
            "flow_definitions": flow_results,
            "errors": errors,
        }

    def execute(self, request: OrchestrationExecutionRequest) -> ProcessExecutionResult:
        """Execute a confirmed flow/process through LangGraph or the linear engine."""
        process, definition_type, definition_id = self._resolve_process(request)
        self.node_definition_model.policy.validate(definition_type, definition_id, process.execution_nodes)
        flow = self._resolve_flow(request.flow_id)
        instance = self._resolve_or_start_instance(request, process, definition_type, definition_id)
        rule_gates = self._applicable_rule_gates(process, flow)
        start_node = request.resume_from_node_id or self._first_node(process).node_id
        state: OrchestrationExecutionState = {
            "definition_type": definition_type,
            "definition_id": definition_id,
            "instance_id": instance.instance_id,
            "flow_id": request.flow_id,
            "process_id": process.process_id,
            "process": process,
            "flow": flow,
            "current_node_id": start_node,
            "status": "running",
            "waiting_for": [],
            "data": dict(request.data or {}),
            "events": [],
            "workflow_trace": [],
            "rule_gates": [rule.model_dump(mode="json") for rule in rule_gates],
        }
        blocked = self._validate_rule_gates(state, rule_gates)
        if blocked is not None:
            return blocked
        if request.use_langgraph:
            try:
                return self._execute_with_langgraph(state)
            except RuntimeError:
                return self._execute_linear(state)
        return self._execute_linear(state)

    def _validate_rule_gates(
        self,
        state: OrchestrationExecutionState,
        rule_gates: list[EnterpriseAsset],
    ) -> ProcessExecutionResult | None:
        if not rule_gates:
            return None
        missing: list[str] = []
        for rule in rule_gates:
            gate = rule.payload.get("gate") if isinstance(rule.payload, dict) else None
            if not isinstance(gate, dict) or gate.get("applies_before_execution") is not True:
                continue
            missing.extend(
                value
                for value in gate.get("required_data", [])
                if value not in state["data"]
            )
        unique_missing = sorted(set(missing))
        self._append_workflow_trace(
            state,
            "rule_gate_check",
            {
                "rules": [rule.asset_id for rule in rule_gates],
                "missing_data": unique_missing,
                "status": "waiting_for_user_input" if unique_missing else "passed",
            },
        )
        if not unique_missing:
            return None
        state["status"] = "waiting_for_user_input"
        state["waiting_for"] = unique_missing
        state["events"].append(
            ProcessExecutionEvent(
                node_id="rule_gate",
                status="waiting_for_user_input",
                message="Business rule gate requires data before process execution.",
                data={
                    "waiting_for": unique_missing,
                    "rules": [rule.asset_id for rule in rule_gates],
                },
            )
        )
        return self._result_from_state(state)

    def _resolve_or_start_instance(
        self,
        request: OrchestrationExecutionRequest,
        process: ProcessDefinition,
        definition_type: Literal["flow", "process"],
        definition_id: str,
    ) -> OrchestratorInstance:
        if request.instance_id:
            existing = self.orchestrator_service.repository.get_instance(request.instance_id)
            if existing is not None:
                return existing
        instance = self.orchestrator_service.start_process_instance(
            process,
            definition_type=definition_type,
            definition_id=definition_id,
            data=dict(request.data or {}),
        )
        return self.orchestrator_service.create_pending_jobs(process, instance)

    def _execute_with_langgraph(self, state: OrchestrationExecutionState) -> ProcessExecutionResult:
        graph_module = self._optional_import("langgraph.graph", "langgraph")
        StateGraph = graph_module.StateGraph
        START = graph_module.START
        END = graph_module.END

        builder = StateGraph(OrchestrationExecutionState)
        self._append_workflow_trace(
            state,
            "workflow_compile",
            {
                "engine": "langgraph",
                "nodes": ["execute_current_node"],
                "edges": [
                    {"from": "__start__", "to": "execute_current_node"},
                    {"from": "execute_current_node", "to": "execute_current_node", "condition": "continue"},
                    {"from": "execute_current_node", "to": "__end__", "condition": "stop"},
                ],
                "checkpointer": None,
            },
        )
        builder.add_node("execute_current_node", self._langgraph_execute_current_node)
        builder.add_edge(START, "execute_current_node")
        builder.add_conditional_edges(
            "execute_current_node",
            self._route_after_node,
            {
                "continue": "execute_current_node",
                "stop": END,
            },
        )
        app = builder.compile()
        final_state = app.invoke(state)
        return self._result_from_state(final_state)

    def _execute_linear(self, state: OrchestrationExecutionState) -> ProcessExecutionResult:
        self._append_workflow_trace(
            state,
            "workflow_compile",
            {
                "engine": "linear",
                "nodes": ["execute_current_node"],
                "checkpointer": None,
            },
        )
        while state.get("status") == "running":
            state = self._execute_current_node(state)
            if self._route_after_node(state) == "stop":
                break
        return self._result_from_state(state)

    def _langgraph_execute_current_node(self, state: OrchestrationExecutionState) -> OrchestrationExecutionState:
        return self._execute_current_node(state)

    def _execute_current_node(self, state: OrchestrationExecutionState) -> OrchestrationExecutionState:
        process = state["process"]
        node = self._node_by_id(process, state["current_node_id"])
        self._append_workflow_trace(
            state,
            "node_started",
            {"node_id": node.node_id, "node_type": node.type, "name": node.name},
        )
        handler = self.node_definition_model.handlers.handler_for(node.type)
        if handler is not None:
            return handler.handle(self, state, node)
        raise OrchestrationExecutionError(f"Unsupported process node type: {node.type}")

    def _wait_for_user_input(self, state: OrchestrationExecutionState, node: ProcessExecutionNode) -> OrchestrationExecutionState:
        missing = [value for value in node.required_inputs if value not in state["data"]]
        if missing:
            return self._waiting(state, node, missing, "Waiting for user information.")
        return self._complete_node(state, node, "User information received.", self._node_outputs(node, state["data"]))

    def _execute_service_call(self, state: OrchestrationExecutionState, node: ProcessExecutionNode) -> OrchestrationExecutionState:
        process = state["process"]
        missing = [value for value in node.required_inputs if value not in state["data"]]
        if missing:
            return self._waiting(state, node, missing, "Service call input data is required.")
        if node.integration_id is None:
            return self._complete_node(state, node, "Service node has no integration; skipped external call.", {})
        integration = self._integration_by_id(process, node.integration_id)
        if integration.requires_approval and not bool(state["data"].get(f"{integration.integration_id}_approved")):
            return self._waiting(
                state,
                node,
                [f"{integration.integration_id}_approved"],
                "Integration requires approval before execution.",
            )
        output = self.integration_registry.execute(integration, node, state["data"])
        return self._complete_node(state, node, "Integration executed.", output)

    def _complete_node(
        self,
        state: OrchestrationExecutionState,
        node: ProcessExecutionNode,
        message: str,
        output: dict[str, Any],
    ) -> OrchestrationExecutionState:
        state["data"].update(output)
        state["events"].append(
            ProcessExecutionEvent(node_id=node.node_id, status="completed", message=message, data=output)
        )
        next_node_id = self._next_node_id(state["process"], node, state["data"])
        self._append_workflow_trace(
            state,
            "node_completed",
            {
                "node_id": node.node_id,
                "node_type": node.type,
                "message": message,
                "next_node_id": next_node_id,
                "output_keys": sorted(output),
            },
        )
        if next_node_id is None:
            state["status"] = "completed"
            state["current_node_id"] = node.node_id
        else:
            state["current_node_id"] = next_node_id
        return state

    def _waiting(
        self,
        state: OrchestrationExecutionState,
        node: ProcessExecutionNode,
        missing: list[str],
        message: str,
    ) -> OrchestrationExecutionState:
        state["status"] = "waiting_for_user_input"
        state["waiting_for"] = missing
        state["current_node_id"] = node.node_id
        state["events"].append(
            ProcessExecutionEvent(
                node_id=node.node_id,
                status="waiting_for_user_input",
                message=message,
                data={"waiting_for": missing},
            )
        )
        self._append_workflow_trace(
            state,
            "node_waiting",
            {
                "node_id": node.node_id,
                "node_type": node.type,
                "waiting_for": missing,
                "message": message,
            },
        )
        if state.get("instance_id"):
            self.orchestrator_service.mark_waiting(state["instance_id"], node.node_id, missing)
        return state

    def _route_after_node(self, state: OrchestrationExecutionState) -> str:
        route = "continue" if state.get("status") == "running" else "stop"
        self._append_workflow_trace(
            state,
            "route_decision",
            {
                "route": route,
                "status": state.get("status"),
                "current_node_id": state.get("current_node_id"),
            },
        )
        return route

    def _resolve_process(self, request: OrchestrationExecutionRequest) -> tuple[ProcessDefinition, Literal["flow", "process"], str]:
        if request.flow_id:
            for flow_id, process in self._flow_processes().items():
                if flow_id == request.flow_id:
                    return process, "flow", flow_id
        processes = self._processes()
        if request.process_id:
            for process in processes:
                if process.process_id == request.process_id:
                    return process, "process", process.process_id
        if request.flow_id:
            for process in processes:
                if request.flow_id in process.related_flow_ids:
                    return process, "process", process.process_id
        raise OrchestrationExecutionError("No process definition matched the execution request.")

    def _resolve_flow(self, flow_id: str | None) -> KnowledgeRecord | None:
        if flow_id is None or self.knowledge_base_service is None:
            return None
        for record in self.knowledge_base_service.search([flow_id]):
            if record.flow_id == flow_id:
                return record
        return None

    def _processes(self) -> list[ProcessDefinition]:
        processes: list[ProcessDefinition] = []
        if self.asset_repository is not None:
            for asset in self.asset_repository.list_assets("process"):
                try:
                    processes.append(ProcessDefinition(**asset.payload))
                except ValueError:
                    continue
        return processes

    def _flow_processes(self) -> dict[str, ProcessDefinition]:
        values: dict[str, ProcessDefinition] = {}
        for process in self._processes():
            for flow_id in process.related_flow_ids:
                values[flow_id] = process
        return values

    def _applicable_rule_gates(
        self,
        process: ProcessDefinition,
        flow: KnowledgeRecord | None,
    ) -> list[EnterpriseAsset]:
        if self.asset_repository is None:
            return []
        target_ids = {f"process.{process.process_id}"}
        target_ids.update(f"flow.{flow_id}" for flow_id in process.related_flow_ids)
        if flow is not None:
            target_ids.add(f"flow.{flow.flow_id}")
        rules = []
        for rule in self.asset_repository.list_assets("business_rule"):
            if any(relation.target_asset_id in target_ids for relation in rule.relations):
                rules.append(rule)
        return rules

    def _first_node(self, process: ProcessDefinition) -> ProcessExecutionNode:
        if not process.execution_nodes:
            raise OrchestrationExecutionError(f"Process {process.process_id} has no executable nodes.")
        return process.execution_nodes[0]

    def _node_by_id(self, process: ProcessDefinition, node_id: str | None) -> ProcessExecutionNode:
        for node in process.execution_nodes:
            if node.node_id == node_id:
                return node
        raise OrchestrationExecutionError(f"Process node not found: {node_id}")

    def _integration_by_id(self, process: ProcessDefinition, integration_id: str) -> ProcessIntegration:
        for integration in process.integrations:
            if integration.integration_id == integration_id:
                return integration
        raise OrchestrationExecutionError(f"Process integration not found: {integration_id}")

    def _next_node_id(
        self,
        process: ProcessDefinition,
        node: ProcessExecutionNode,
        data: dict[str, Any],
    ) -> str | None:
        for transition in process.transitions:
            if transition.from_node == node.node_id and self._transition_matches(transition.condition, data):
                return transition.to_node
        if node.on_success:
            return node.on_success
        if node.next_nodes:
            return node.next_nodes[0]
        ordered_nodes = list(process.execution_nodes)
        for index, current in enumerate(ordered_nodes):
            if current.node_id == node.node_id and index + 1 < len(ordered_nodes):
                return ordered_nodes[index + 1].node_id
        return None

    def _transition_matches(self, condition: str, data: dict[str, Any]) -> bool:
        if condition in {"", "always"}:
            return True
        if condition == "required_inputs_present":
            return True
        if condition.startswith("data."):
            key = condition.removeprefix("data.")
            return bool(data.get(key))
        return False

    def _node_outputs(self, node: ProcessExecutionNode, data: dict[str, Any]) -> dict[str, Any]:
        return {key: data.get(key) for key in node.produced_outputs if key in data}

    def _result_from_state(self, state: OrchestrationExecutionState) -> ProcessExecutionResult:
        status = state.get("status")
        if status == "running":
            status = "completed"
        if status not in {"completed", "waiting_for_user_input", "failed"}:
            status = "failed"
        if status == "completed" and state.get("instance_id"):
            self.orchestrator_service.complete_instance(state["instance_id"])
        return ProcessExecutionResult(
            process_id=state["process"].process_id,
            instance_id=state.get("instance_id"),
            status=status,
            current_node_id=state.get("current_node_id"),
            waiting_for=state.get("waiting_for", []),
            data=state.get("data", {}),
            events=state.get("events", []),
            workflow_trace=state.get("workflow_trace", []),
        )

    def _append_workflow_trace(self, state: OrchestrationExecutionState, event: str, payload: dict[str, Any]) -> None:
        trace = state.setdefault("workflow_trace", [])
        trace.append(
            {
                "event": event,
                "instance_id": state.get("instance_id"),
                "process_id": state.get("process_id"),
                **payload,
            }
        )

    def _optional_import(self, module_name: str, friendly_name: str | None = None):
        try:
            return import_module(module_name)
        except ImportError as exc:
            raise RuntimeError(
                f"Optional dependency '{friendly_name or module_name}' is required for this provider."
            ) from exc
