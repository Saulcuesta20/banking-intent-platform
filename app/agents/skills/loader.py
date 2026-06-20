from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from app.agents.skills.models import AgentSkill


@dataclass(frozen=True)
class SkillCatalogLoader:
    """Load Anthropic-style skills from markdown files with YAML frontmatter."""

    def load_directory(self, directory: Path) -> list[AgentSkill]:
        if not directory.exists():
            return []
        skills: list[AgentSkill] = []
        for skill_file in sorted(directory.glob("*/SKILL.md")):
            skills.append(self.load_file(skill_file))
        return skills

    def load_file(self, path: Path) -> AgentSkill:
        text = path.read_text(encoding="utf-8")
        frontmatter, body = self._split_frontmatter(text, path)
        metadata = yaml.safe_load(frontmatter) or {}
        if not isinstance(metadata, dict):
            raise ValueError(f"Skill frontmatter must be a YAML object: {path}")
        skill_id = str(metadata.get("name") or path.parent.name)
        description = str(metadata.get("description") or "").strip()
        if not description:
            raise ValueError(f"Skill frontmatter requires a description: {path}")
        allowed_tools = metadata.get("allowed-tools") or metadata.get("allowed_tools") or []
        if isinstance(allowed_tools, str):
            allowed_tools = [allowed_tools]
        if not isinstance(allowed_tools, list):
            raise ValueError(f"Skill allowed tools must be a list or string: {path}")
        return AgentSkill(
            skill_id=skill_id,
            name=skill_id,
            description=description,
            instructions=body.strip(),
            path=path,
            allowed_tools=[str(tool) for tool in allowed_tools if str(tool)],
            disable_model_invocation=bool(metadata.get("disable-model-invocation") or metadata.get("disable_model_invocation") or False),
            metadata=metadata,
        )

    def load_index(self, directory: Path) -> dict[str, AgentSkill]:
        return {skill.skill_id: skill for skill in self.load_directory(directory)}

    def _split_frontmatter(self, text: str, path: Path) -> tuple[str, str]:
        if not text.startswith("---"):
            raise ValueError(f"Skill file must start with YAML frontmatter: {path}")
        parts = text.split("---", 2)
        if len(parts) < 3:
            raise ValueError(f"Skill file must contain closing frontmatter fence: {path}")
        _, frontmatter, body = parts
        return frontmatter.strip(), body
