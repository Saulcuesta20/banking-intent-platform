from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

from app.models import ProcessExecutionEvent, ProcessExecutionNode
from app.orchestrator.node_policy import ExecutionNodePolicy

if TYPE_CHECKING:
    from app.orchestrator.orchestration_executor import OrchestrationExecutorService, OrchestrationExecutionState


class NodeHandler(Protocol):
    """Contract for runtime behavior of one execution-node type."""

    def handle(
        self,
        service: OrchestrationExecutorService,
        state: OrchestrationExecutionState,
        node: ProcessExecutionNode,
    ) -> OrchestrationExecutionState:
        ...


@dataclass(frozen=True)
class StartNodeHandler:
    def handle(
        self,
        service: OrchestrationExecutorService,
        state: OrchestrationExecutionState,
        node: ProcessExecutionNode,
    ) -> OrchestrationExecutionState:
        return service._complete_node(state, node, "Process started.", {})


@dataclass(frozen=True)
class UserTaskNodeHandler:
    def handle(
        self,
        service: OrchestrationExecutorService,
        state: OrchestrationExecutionState,
        node: ProcessExecutionNode,
    ) -> OrchestrationExecutionState:
        missing = [value for value in node.required_inputs if value not in state["data"]]
        if missing:
            return service._waiting(state, node, missing, "User task is waiting for required input.")
        payload = service._node_outputs(node, state["data"])
        if node.related_user_task_id:
            payload["related_user_task_id"] = node.related_user_task_id
        payload["wait_state"] = node.wait_state
        if node.user_actions:
            payload["user_actions"] = [action.to_dict() for action in node.user_actions]
        if node.actions:
            payload["actions"] = list(node.actions)
        if node.tools:
            payload["tools"] = list(node.tools)
        return service._complete_node(state, node, "User task node completed.", payload)


@dataclass(frozen=True)
class AgentNodeHandler:
    def handle(
        self,
        service: OrchestrationExecutorService,
        state: OrchestrationExecutionState,
        node: ProcessExecutionNode,
    ) -> OrchestrationExecutionState:
        missing = [value for value in node.required_inputs if value not in state["data"]]
        if missing:
            return service._waiting(state, node, missing, "Agent node is waiting for required input.")
        payload = service._node_outputs(node, state["data"])
        return service._complete_node(state, node, "Agent node completed.", payload)


@dataclass(frozen=True)
class WaitForUserInputNodeHandler:
    def handle(
        self,
        service: OrchestrationExecutorService,
        state: OrchestrationExecutionState,
        node: ProcessExecutionNode,
    ) -> OrchestrationExecutionState:
        missing = [value for value in node.required_inputs if value not in state["data"]]
        if missing:
            return service._waiting(state, node, missing, "Waiting for user information.")
        return service._complete_node(state, node, "User information received.", service._node_outputs(node, state["data"]))


@dataclass(frozen=True)
class StateUpdateNodeHandler:
    def handle(
        self,
        service: OrchestrationExecutorService,
        state: OrchestrationExecutionState,
        node: ProcessExecutionNode,
    ) -> OrchestrationExecutionState:
        return service._complete_node(state, node, "State updated.", service._node_outputs(node, state["data"]))


@dataclass(frozen=True)
class ServiceCallNodeHandler:
    def handle(
        self,
        service: OrchestrationExecutorService,
        state: OrchestrationExecutionState,
        node: ProcessExecutionNode,
    ) -> OrchestrationExecutionState:
        return service._execute_service_call(state, node)


@dataclass(frozen=True)
class DecisionNodeHandler:
    def handle(
        self,
        service: OrchestrationExecutorService,
        state: OrchestrationExecutionState,
        node: ProcessExecutionNode,
    ) -> OrchestrationExecutionState:
        return service._complete_node(state, node, "Decision evaluated.", service._node_outputs(node, state["data"]))


@dataclass(frozen=True)
class ApprovalNodeHandler:
    def handle(
        self,
        service: OrchestrationExecutorService,
        state: OrchestrationExecutionState,
        node: ProcessExecutionNode,
    ) -> OrchestrationExecutionState:
        missing = [value for value in node.required_inputs if value not in state["data"]]
        if missing:
            return service._waiting(state, node, missing, "Approval data is required.")
        return service._complete_node(state, node, "Approval recorded.", service._node_outputs(node, state["data"]))


@dataclass(frozen=True)
class NotificationNodeHandler:
    def handle(
        self,
        service: OrchestrationExecutorService,
        state: OrchestrationExecutionState,
        node: ProcessExecutionNode,
    ) -> OrchestrationExecutionState:
        return service._complete_node(state, node, "Notification prepared.", service._node_outputs(node, state["data"]))


@dataclass(frozen=True)
class EndNodeHandler:
    def handle(
        self,
        service: OrchestrationExecutorService,
        state: OrchestrationExecutionState,
        node: ProcessExecutionNode,
    ) -> OrchestrationExecutionState:
        state["status"] = "completed"
        state["events"].append(
            ProcessExecutionEvent(node_id=node.node_id, status="completed", message="Process completed.")
        )
        return state


@dataclass
class NodeHandlerRegistry:
    """Node-type to handler map for execution runtime."""

    handlers: dict[str, NodeHandler] = field(default_factory=dict)

    @classmethod
    def with_defaults(cls) -> "NodeHandlerRegistry":
        service_call = ServiceCallNodeHandler()
        return cls(
            handlers={
                "start": StartNodeHandler(),
                "user_task": UserTaskNodeHandler(),
                "agent": AgentNodeHandler(),
                "wait_for_user_input": WaitForUserInputNodeHandler(),
                "state_update": StateUpdateNodeHandler(),
                "service_call": service_call,
                "tool_call": service_call,
                "subprocess_call": service_call,
                "decision": DecisionNodeHandler(),
                "approval": ApprovalNodeHandler(),
                "notification": NotificationNodeHandler(),
                "end": EndNodeHandler(),
            }
        )

    def handler_for(self, node_type: str) -> NodeHandler | None:
        return self.handlers.get(node_type)


@dataclass
class NodeDefinitionModel:
    """Runtime configuration: allowed node policy plus behavior handlers."""

    policy: ExecutionNodePolicy = field(default_factory=ExecutionNodePolicy)
    handlers: NodeHandlerRegistry = field(default_factory=NodeHandlerRegistry.with_defaults)
