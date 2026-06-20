from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AgentSkill:
    """Anthropic-style skill package loaded from a SKILL.md file."""

    skill_id: str
    name: str
    description: str
    instructions: str
    path: Path
    allowed_tools: list[str] = field(default_factory=list)
    disable_model_invocation: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def preview(self, limit: int = 200) -> str:
        text = " ".join(self.instructions.split())
        return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"
