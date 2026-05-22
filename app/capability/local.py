from __future__ import annotations

from app.capability.providers import CapabilityProvider
from app.models import ActionRegistryEntry, KnowledgeRecord, Task


class LocalCapabilityProvider(CapabilityProvider):
    def __init__(self, records: list[KnowledgeRecord] | None = None):
        self.action_registry = self.build_action_registry(records or [])

    def find_for_record(self, record: KnowledgeRecord, tasks: list[Task]) -> list[str]:
        capabilities: list[str] = []
        seen: set[str] = set()
        for value in record.capabilities:
            self._append_unique(capabilities, seen, value)
        for user_task in record.user_tasks:
            for action in user_task.front_actions:
                self._append_unique(capabilities, seen, action.action)
            for action in user_task.back_actions:
                self._append_unique(capabilities, seen, action.action)
        return capabilities

    def list_registered_actions(self) -> list[ActionRegistryEntry]:
        return list(self.action_registry)

    def build_action_registry(self, records: list[KnowledgeRecord]) -> list[ActionRegistryEntry]:
        entries: dict[tuple[str, str], dict[str, object]] = {}
        for record in records:
            for user_task in record.user_tasks:
                for action in [*user_task.front_actions, *user_task.back_actions]:
                    key = (action.type, action.action)
                    entry = entries.setdefault(
                        key,
                        {
                            **action.to_dict(),
                            "user_tasks": set(),
                            "flows": set(),
                        },
                    )
                    entry["user_tasks"].add(user_task.user_task_id or user_task.task)
                    entry["flows"].add(record.flow_id)

        registry = []
        for entry in entries.values():
            registry.append(
                ActionRegistryEntry(
                    action=str(entry["action"]),
                    type=entry["type"],
                    operation=entry.get("operation"),
                    resource=entry.get("resource"),
                    label=entry.get("label"),
                    triggers=entry.get("triggers"),
                    description=entry.get("description"),
                    user_tasks=sorted(entry["user_tasks"]),
                    flows=sorted(entry["flows"]),
                )
            )
        return sorted(registry, key=lambda item: (item.type, item.action))

    def _append_unique(self, values: list[str], seen: set[str], value: str) -> None:
        if value not in seen:
            values.append(value)
            seen.add(value)
