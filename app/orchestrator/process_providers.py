from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from app.models import ProcessExecutionNode, ProcessIntegration


class IntegrationProvider(Protocol):
    """Port for backend protocol adapters used by process integrations."""

    def execute(
        self,
        integration: ProcessIntegration,
        node: ProcessExecutionNode,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute one process integration and return state updates."""


@dataclass(frozen=True)
class IntegrationProviderRegistry:
    """Registry that dispatches process integrations to protocol providers."""

    providers: dict[str, IntegrationProvider] = field(default_factory=dict)

    def execute(
        self,
        integration: ProcessIntegration,
        node: ProcessExecutionNode,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute one integration using the matching provider or simulator."""
        provider = self.providers.get(integration.protocol)
        if provider is None:
            provider = SimulatedIntegrationProvider()
        return provider.execute(integration, node, data)


class SimulatedIntegrationProvider:
    """Safe default provider used before real API/gRPC/MCP adapters exist."""

    def execute(
        self,
        integration: ProcessIntegration,
        node: ProcessExecutionNode,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Return a deterministic simulated integration result."""
        return {
            node.node_id: {
                "integration_id": integration.integration_id,
                "protocol": integration.protocol,
                "endpoint": integration.endpoint,
                "operation": integration.operation,
                "simulated": True,
            }
        }
