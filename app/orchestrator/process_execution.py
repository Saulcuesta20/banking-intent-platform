from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any, NotRequired, TypedDict

from app.ingestion.flow_loader import FlowKnowledgeLoader
from app.ingestion.process_loader import ProcessDefinitionLoader
from app.models import (
    KnowledgeRecord,
    OrchestratorInstance,
    ProcessDefinition,
    ProcessExecutionNode,
    ProcessExecutionEvent,
    ProcessExecutionResult,
    ProcessIntegration,
)
from app.orchestrator.service import OrchestratorService
from app.orchestrator.process_providers import IntegrationProviderRegistry


class ProcessExecutionError(RuntimeError):
    pass


class ProcessExecutionState(TypedDict, total=False):
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
    error: NotRequired[str]


@dataclass(frozen=True)
class ProcessExecutionRequest:
    flow_id: str | None = None
    process_id: str | None = None
    instance_id: str | None = None
    data: dict[str, Any] | None = None
    resume_from_node_id: str | None = None
    use_langgraph: bool = True


class ProcessExecutionService:
    """Execute process nodes from flow/process definitions.

    LangGraph owns orchestration when available. Node bodies stay deterministic
    and delegate protocol calls through provider adapters.
    """

    def __init__(
        self,
        flow_directory: Path,
        process_directory: Path,
        integration_registry: IntegrationProviderRegistry | None = None,
        orchestrator_service: OrchestratorService | None = None,
    ):
        self.flow_loader = FlowKnowledgeLoader()
        self.process_loader = ProcessDefinitionLoader()
        self.flow_directory = flow_directory
        self.process_directory = process_directory
        self.integration_registry = integration_registry or IntegrationProviderRegistry()
        self.orchestrator_service = orchestrator_service or OrchestratorService()

    def execute(self, request: ProcessExecutionRequest) -> ProcessExecutionResult:
        process = self._resolve_process(request)
        flow = self._resolve_flow(request.flow_id)
        instance = self._resolve_or_start_instance(request, process)
        start_node = request.resume_from_node_id or self._first_node(process).node_id
        state: ProcessExecutionState = {
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
        }
        if request.use_langgraph:
            try:
                return self._execute_with_langgraph(state)
            except RuntimeError:
                return self._execute_linear(state)
        return self._execute_linear(state)

    def _resolve_or_start_instance(
        self,
        request: ProcessExecutionRequest,
        process: ProcessDefinition,
    ) -> OrchestratorInstance:
        if request.instance_id:
            existing = self.orchestrator_service.repository.get_instance(request.instance_id)
            if existing is not None:
                return existing
        instance = self.orchestrator_service.start_process_instance(
            process,
            data=dict(request.data or {}),
        )
        return self.orchestrator_service.create_pending_jobs(process, instance)

    def _execute_with_langgraph(self, state: ProcessExecutionState) -> ProcessExecutionResult:
        graph_module = self._optional_import("langgraph.graph", "langgraph")
        StateGraph = graph_module.StateGraph
        START = graph_module.START
        END = graph_module.END

        builder = StateGraph(ProcessExecutionState)
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

    def _execute_linear(self, state: ProcessExecutionState) -> ProcessExecutionResult:
        while state.get("status") == "running":
            state = self._execute_current_node(state)
            if self._route_after_node(state) == "stop":
                break
        return self._result_from_state(state)

    def _langgraph_execute_current_node(self, state: ProcessExecutionState) -> ProcessExecutionState:
        return self._execute_current_node(state)

    def _execute_current_node(self, state: ProcessExecutionState) -> ProcessExecutionState:
        process = state["process"]
        node = self._node_by_id(process, state["current_node_id"])
        if node.type == "start":
            return self._complete_node(state, node, "Process started.", {})
        if node.type == "wait_for_user_input":
            return self._wait_for_user_input(state, node)
        if node.type == "state_update":
            return self._complete_node(state, node, "State updated.", self._node_outputs(node, state["data"]))
        if node.type == "service_call":
            return self._execute_service_call(state, node)
        if node.type == "decision":
            return self._complete_node(state, node, "Decision evaluated.", self._node_outputs(node, state["data"]))
        if node.type == "approval":
            missing = [value for value in node.required_inputs if value not in state["data"]]
            if missing:
                return self._waiting(state, node, missing, "Approval data is required.")
            return self._complete_node(state, node, "Approval recorded.", self._node_outputs(node, state["data"]))
        if node.type == "notification":
            return self._complete_node(state, node, "Notification prepared.", self._node_outputs(node, state["data"]))
        if node.type == "end":
            state["status"] = "completed"
            state["events"].append(ProcessExecutionEvent(node_id=node.node_id, status="completed", message="Process completed."))
            return state
        raise ProcessExecutionError(f"Unsupported process node type: {node.type}")

    def _wait_for_user_input(self, state: ProcessExecutionState, node: ProcessExecutionNode) -> ProcessExecutionState:
        missing = [value for value in node.required_inputs if value not in state["data"]]
        if missing:
            return self._waiting(state, node, missing, "Waiting for user information.")
        return self._complete_node(state, node, "User information received.", self._node_outputs(node, state["data"]))

    def _execute_service_call(self, state: ProcessExecutionState, node: ProcessExecutionNode) -> ProcessExecutionState:
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
        state: ProcessExecutionState,
        node: ProcessExecutionNode,
        message: str,
        output: dict[str, Any],
    ) -> ProcessExecutionState:
        state["data"].update(output)
        state["events"].append(
            ProcessExecutionEvent(node_id=node.node_id, status="completed", message=message, data=output)
        )
        next_node_id = self._next_node_id(state["process"], node, state["data"])
        if next_node_id is None:
            state["status"] = "completed"
            state["current_node_id"] = node.node_id
        else:
            state["current_node_id"] = next_node_id
        return state

    def _waiting(
        self,
        state: ProcessExecutionState,
        node: ProcessExecutionNode,
        missing: list[str],
        message: str,
    ) -> ProcessExecutionState:
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
        if state.get("instance_id"):
            self.orchestrator_service.mark_waiting(state["instance_id"], node.node_id, missing)
        return state

    def _route_after_node(self, state: ProcessExecutionState) -> str:
        return "continue" if state.get("status") == "running" else "stop"

    def _resolve_process(self, request: ProcessExecutionRequest) -> ProcessDefinition:
        processes = self.process_loader.load_directory(self.process_directory)
        if request.process_id:
            for process in processes:
                if process.process_id == request.process_id:
                    return process
        if request.flow_id:
            for process in processes:
                if request.flow_id in process.related_flow_ids:
                    return process
        raise ProcessExecutionError("No process definition matched the execution request.")

    def _resolve_flow(self, flow_id: str | None) -> KnowledgeRecord | None:
        if flow_id is None:
            return None
        for record in self.flow_loader.load_directory(self.flow_directory):
            if record.flow_id == flow_id:
                return record
        return None

    def _first_node(self, process: ProcessDefinition) -> ProcessExecutionNode:
        if not process.execution_nodes:
            raise ProcessExecutionError(f"Process {process.process_id} has no executable nodes.")
        return process.execution_nodes[0]

    def _node_by_id(self, process: ProcessDefinition, node_id: str | None) -> ProcessExecutionNode:
        for node in process.execution_nodes:
            if node.node_id == node_id:
                return node
        raise ProcessExecutionError(f"Process node not found: {node_id}")

    def _integration_by_id(self, process: ProcessDefinition, integration_id: str) -> ProcessIntegration:
        for integration in process.integrations:
            if integration.integration_id == integration_id:
                return integration
        raise ProcessExecutionError(f"Process integration not found: {integration_id}")

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

    def _result_from_state(self, state: ProcessExecutionState) -> ProcessExecutionResult:
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
        )

    def _optional_import(self, module_name: str, friendly_name: str | None = None):
        try:
            return import_module(module_name)
        except ImportError as exc:
            raise RuntimeError(
                f"Optional dependency '{friendly_name or module_name}' is required for this provider."
            ) from exc
