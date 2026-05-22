from __future__ import annotations

from app.capability.providers import CapabilityProvider
from app.models import ActionRegistryEntry, KnowledgeRecord, Task


class CapabilityService:
    def __init__(self, provider: CapabilityProvider):
        self.provider = provider

    def find_related_capabilities(self, record: KnowledgeRecord, tasks: list[Task]) -> list[str]:
        return self.provider.find_for_record(record, tasks)

    def build_action_registry(self, records: list[KnowledgeRecord]) -> list[ActionRegistryEntry]:
        return self.provider.build_action_registry(records)

    def list_registered_actions(self) -> list[ActionRegistryEntry]:
        return self.provider.list_registered_actions()
