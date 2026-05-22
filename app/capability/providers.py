from __future__ import annotations

from typing import Protocol

from app.models import ActionRegistryEntry, KnowledgeRecord, Task


class CapabilityProvider(Protocol):
    def find_for_record(self, record: KnowledgeRecord, tasks: list[Task]) -> list[str]:
        """Return action capabilities related to a resolved flow and its user tasks."""

    def build_action_registry(self, records: list[KnowledgeRecord]) -> list[ActionRegistryEntry]:
        """Return the unified front/back action registry derived from loaded flows."""

    def list_registered_actions(self) -> list[ActionRegistryEntry]:
        """Return the front/back actions registered when the component starts."""
