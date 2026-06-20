from __future__ import annotations

from dataclasses import dataclass, field

from app.capability.providers import CapabilityProvider
from app.models import ActionRegistryEntry, KnowledgeRecord, Task
from app.tools.models import ToolRegistryEntry
from app.tools.registry import ToolRegistryProvider


@dataclass
class RegistryCapabilityProvider(CapabilityProvider):
    """Build tool capability lookups from loaded flow and user-task records."""

    records: list[KnowledgeRecord] = field(default_factory=list)
    tool_registry: list[ToolRegistryEntry] = field(init=False)
    action_registry: list[ActionRegistryEntry] = field(init=False)

    def __post_init__(self) -> None:
        """Build canonical and legacy registries from the provided records."""
        self.tool_registry = ToolRegistryProvider(self.records).list_registered_tools()
        self.action_registry = self._legacy_action_registry(self.tool_registry)

    def find_for_record(self, record: KnowledgeRecord, tasks: list[Task]) -> list[str]:
        """Return unique tool ids declared by the selected flow and tasks."""
        capabilities: list[str] = []
        seen: set[str] = set()
        for value in record.capabilities:
            self._append_unique(capabilities, seen, value)
        for user_task in record.user_tasks:
            for tool in user_task.tools:
                self._append_unique(capabilities, seen, tool.tool_id)
        return capabilities

    def list_registered_actions(self) -> list[ActionRegistryEntry]:
        """Return the deprecated action view for compatibility callers."""
        return list(self.action_registry)

    def list_registered_tools(self) -> list[ToolRegistryEntry]:
        """Return the canonical tool registry."""
        return list(self.tool_registry)

    def build_action_registry(self, records: list[KnowledgeRecord]) -> list[ActionRegistryEntry]:
        """Build the deprecated action registry from canonical tool definitions."""
        entries: dict[tuple[str, str], dict[str, object]] = {}
        for record in records:
            for user_task in record.user_tasks:
                for tool in user_task.tools:
                    legacy = tool.to_dict()
                    legacy_type = "front" if tool.tool_type == "frontend_tool" else "back"
                    if tool.tool_type == "llm_tool":
                        continue
                    key = (legacy_type, tool.tool_id)
                    entry = entries.setdefault(
                        key,
                        {
                            "action_id": tool.tool_id,
                            "type": legacy_type,
                            "implementation_type": "show_form" if tool.tool_type == "frontend_tool" else ("llm_tool" if tool.tool_type == "llm_tool" else "tool_call"),
                            "tool_id": tool.tool_id if tool.tool_type != "frontend_tool" else None,
                            "tool_ids": [tool.tool_id],
                            "label": legacy.get("label"),
                            "triggers": legacy.get("triggers") or legacy.get("frontend_event"),
                            "description": legacy.get("description"),
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
                    action_id=str(entry["action_id"]),
                    type=entry["type"],
                    implementation_type=entry.get("implementation_type") or "custom",
                    tool_id=entry.get("tool_id"),
                    tool_ids=sorted(entry.get("tool_ids") or []),
                    label=entry.get("label"),
                    triggers=entry.get("triggers"),
                    description=entry.get("description"),
                    user_tasks=sorted(entry["user_tasks"]),
                    flows=sorted(entry["flows"]),
                )
            )
        return sorted(registry, key=lambda item: (item.type, item.action))

    def _legacy_action_registry(self, tools: list[ToolRegistryEntry]) -> list[ActionRegistryEntry]:
        registry = []
        for tool in tools:
            if tool.tool_type == "llm_tool":
                continue
            legacy = tool.to_legacy_action_dict()
            registry.append(
                ActionRegistryEntry(
                    action_id=str(legacy["action"]),
                    type=legacy["type"],
                    implementation_type=legacy.get("implementation_type") or "custom",
                    tool_id=legacy.get("tool_id"),
                    tool_ids=legacy.get("tool_ids") or ([legacy["tool_id"]] if legacy.get("tool_id") else []),
                    label=legacy.get("label"),
                    triggers=legacy.get("triggers"),
                    description=legacy.get("description"),
                    user_tasks=legacy["user_tasks"],
                    flows=legacy["flows"],
                )
            )
        return sorted(registry, key=lambda item: (item.type, item.action))

    def _append_unique(self, values: list[str], seen: set[str], value: str) -> None:
        if value not in seen:
            values.append(value)
            seen.add(value)
