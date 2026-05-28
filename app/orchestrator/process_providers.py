from __future__ import annotations

from typing import Any, Protocol

from app.models import ProcessExecutionNode, ProcessIntegration


class IntegrationProvider(Protocol):
    def execute(
        self,
        integration: ProcessIntegration,
        node: ProcessExecutionNode,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute one process integration and return state updates."""


class IntegrationProviderRegistry:
    def __init__(self, providers: dict[str, IntegrationProvider] | None = None):
        self.providers = providers or {}

    def execute(
        self,
        integration: ProcessIntegration,
        node: ProcessExecutionNode,
        data: dict[str, Any],
    ) -> dict[str, Any]:
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
        return {
            node.node_id: {
                "integration_id": integration.integration_id,
                "protocol": integration.protocol,
                "endpoint": integration.endpoint,
                "operation": integration.operation,
                "simulated": True,
            }
        }
