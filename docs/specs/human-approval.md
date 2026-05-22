# Human Approval

## Purpose
Ensure every proposed banking action requires human approval.

## Responsibilities
- Mark all outputs with `requires_human_approval: true`.
- Add approval tasks to plans.
- Prevent automated execution.

## Main Components
- `ApprovalService`
- `app/approval/providers.py::ApprovalProvider`
- `app/approval/policy.py::AlwaysHumanApprovalPolicy`
- Approval task model
- Guardrail validator

## Data Flow
Planning and decomposition results are passed through `ApprovalService` before output serialization.

## Example Input/Output
Input plan: `prepare_refinance_request`

Output includes `approve_business_case` in the plan and an approval user task when missing.

## Interfaces
- `ApprovalService.requires_approval()`
- `ApprovalService.enforce(plan, tasks)`
- `ApprovalProvider.enforce(plan, tasks)`

## Implementation Notes
The MVP uses an always-true approval policy in `app/approval/policy.py`. The component is wired in `app/factory.py`.

## Future Replacement Strategy
Future versions may add approval levels, roles, and workflow integration while preserving the default no-execution rule.
