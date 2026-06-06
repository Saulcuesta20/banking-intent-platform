from __future__ import annotations

from dataclasses import dataclass, field

from app.models import KnowledgeRecord
from app.tools.models import ToolRegistryEntry


@dataclass
class ToolRegistryProvider:
    """Build the canonical tool registry from loaded flow/user-task assets."""

    records: list[KnowledgeRecord] = field(default_factory=list)
    tool_registry: list[ToolRegistryEntry] = field(init=False)

    def __post_init__(self) -> None:
        """Build the in-memory registry once records are assigned."""
        self.tool_registry = self.build_tool_registry(self.records)

    def list_registered_tools(self) -> list[ToolRegistryEntry]:
        """Return registered tools in deterministic order."""
        return list(self.tool_registry)

    def build_tool_registry(self, records: list[KnowledgeRecord]) -> list[ToolRegistryEntry]:
        """Collect unique tools and attach their user-task and flow owners."""
        entries: dict[tuple[str, str], ToolRegistryEntry] = {}
        user_tasks_by_key: dict[tuple[str, str], set[str]] = {}
        flows_by_key: dict[tuple[str, str], set[str]] = {}

        for record in records:
            for user_task in record.user_tasks:
                for item in user_task.tools:
                    tool = ToolRegistryEntry(
                        **item.model_dump(mode="json"),
                        user_tasks=[user_task.user_task_id or user_task.task],
                        flows=[record.flow_id],
                    )
                    key = (tool.tool_type, tool.tool_id)
                    entries.setdefault(key, tool)
                    user_tasks_by_key.setdefault(key, set()).update(tool.user_tasks)
                    flows_by_key.setdefault(key, set()).update(tool.flows)

        registry = []
        for key, tool in entries.items():
            registry.append(
                tool.model_copy(
                    update={
                        "user_tasks": sorted(user_tasks_by_key[key]),
                        "flows": sorted(flows_by_key[key]),
                    }
                )
            )
        return sorted(registry, key=lambda item: (item.tool_type, item.tool_id))
