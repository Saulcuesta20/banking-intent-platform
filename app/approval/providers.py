from __future__ import annotations

from typing import Protocol

from app.models import Task


class ApprovalProvider(Protocol):
    def requires_approval(self) -> bool:
        """Return whether the response requires human approval."""

    def enforce(self, plan: list[str], tasks: list[Task]) -> tuple[list[str], list[Task]]:
        """Ensure approval markers are present in plan and tasks."""
