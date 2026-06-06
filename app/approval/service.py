from __future__ import annotations

from dataclasses import dataclass

from app.approval.providers import ApprovalProvider
from app.models import Task


@dataclass(frozen=True)
class ApprovalService:
    """Application service that applies the configured approval policy."""

    provider: ApprovalProvider

    def requires_approval(self) -> bool:
        """Return whether the active approval policy requires approval."""
        return self.provider.requires_approval()

    def enforce(self, plan: list[str], tasks: list[Task]) -> tuple[list[str], list[Task]]:
        """Apply approval policy to a projected plan and task list."""
        return self.provider.enforce(plan, tasks)
