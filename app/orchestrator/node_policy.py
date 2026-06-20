from __future__ import annotations

from dataclasses import dataclass, field

from app.config.model import load_node_policy
from app.models import ProcessExecutionNode


class NodePolicyError(RuntimeError):
    """Raised when a definition includes nodes not allowed for its type."""

    pass


@dataclass(frozen=True)
class ExecutionNodePolicy:
    """Python-side policy for allowed execution node types by definition type."""

    allowed_types: dict[str, set[str]] = field(
        default_factory=load_node_policy
    )

    def validate(self, definition_type: str, definition_id: str, nodes: list[ProcessExecutionNode]) -> None:
        allowed = self.allowed_types.get(definition_type)
        if allowed is None:
            raise NodePolicyError(f"Unknown definition type for node policy: {definition_type}")
        invalid = sorted({node.type for node in nodes if node.type not in allowed})
        if invalid:
            raise NodePolicyError(
                f"{definition_type}.{definition_id} defines unsupported node types: {', '.join(invalid)}"
            )
