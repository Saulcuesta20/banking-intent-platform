from __future__ import annotations

from app.approval.providers import ApprovalProvider
from app.models import Task


class ApprovalService:
    def __init__(self, provider: ApprovalProvider):
        self.provider = provider

    def requires_approval(self) -> bool:
        return self.provider.requires_approval()

    def enforce(self, plan: list[str], tasks: list[Task]) -> tuple[list[str], list[Task]]:
        return self.provider.enforce(plan, tasks)
