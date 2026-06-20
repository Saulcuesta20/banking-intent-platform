from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.agents.models import AgentDefinition, AgentPolicy


class AgentCatalogLoader:
    """Load declarative agent definitions from YAML."""

    def load_file(self, path: Path) -> list[AgentDefinition]:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        if payload is None:
            return []
        if isinstance(payload, dict):
            entries = payload.get("agents") or []
        elif isinstance(payload, list):
            entries = payload
        else:
            raise ValueError(f"Agent catalog YAML must contain an object or list: {path}")
        if not isinstance(entries, list):
            raise ValueError(f"Agent catalog YAML must contain an agents list: {path}")
        return [self._load_entry(entry, path) for entry in entries]

    def load_dict(self, payload: dict[str, Any] | list[dict[str, Any]]) -> list[AgentDefinition]:
        if isinstance(payload, dict):
            entries = payload.get("agents") or []
        else:
            entries = payload
        if not isinstance(entries, list):
            raise ValueError("Agent catalog payload must contain an agents list")
        return [self._load_entry(entry, Path("agent_catalog.yaml")) for entry in entries]

    def _load_entry(self, entry: Any, path: Path) -> AgentDefinition:
        if not isinstance(entry, dict):
            raise ValueError(f"Agent catalog entries must be objects: {path}")
        data = dict(entry)
        policy_payload = data.get("policy") or {}
        skill_ids = [str(skill_id) for skill_id in data.pop("skill_ids", []) if str(skill_id)]
        tool_ids = [str(tool_id) for tool_id in data.pop("tool_ids", []) if str(tool_id)]
        policy = AgentPolicy.model_validate(policy_payload)
        if tool_ids and not policy.allowed_tool_ids:
            policy = policy.model_copy(update={"allowed_tool_ids": tool_ids})
        data["policy"] = policy
        data["skill_ids"] = skill_ids
        data["tool_ids"] = tool_ids or list(policy.allowed_tool_ids)
        return AgentDefinition.model_validate(data)
