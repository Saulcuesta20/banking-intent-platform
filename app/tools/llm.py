from __future__ import annotations

from typing import Any, Protocol

from app.tools.models import ToolDefinition


class LLMToolClient(Protocol):
    """Protocol for LLM-backed tools that return structured JSON."""

    tool_definition: ToolDefinition

    def complete_json(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Invoke the LLM tool and return parsed JSON."""
