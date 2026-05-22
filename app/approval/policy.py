from __future__ import annotations

from app.approval.providers import ApprovalProvider
from app.models import Task


class AlwaysHumanApprovalPolicy(ApprovalProvider):
    def requires_approval(self) -> bool:
        return True

    def enforce(self, plan: list[str], tasks: list[Task]) -> tuple[list[str], list[Task]]:
        guarded_plan = list(plan)
        if "approve_business_case" not in guarded_plan:
            guarded_plan.append("approve_business_case")

        guarded_tasks = list(tasks)
        if not any(task.task == "approve_business_case" for task in guarded_tasks):
            guarded_tasks.append(Task(task="approve_business_case", type="approval"))

        return guarded_plan, guarded_tasks
