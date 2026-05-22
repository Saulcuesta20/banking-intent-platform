# Security Model

## Purpose
Define basic MVP security boundaries for sensitive banking knowledge and AI output.

## Responsibilities
- Avoid automated business execution.
- Keep credentials in environment variables.
- Treat customer data and document contents as sensitive.

## Main Components
- Configuration model
- Provider credential handling
- Approval service and provider
- Audit redaction policy

## Data Flow
Inputs pass through application services, provider calls use environment configuration, and outputs expose only planning information.

## Example Input/Output
Input: customer request containing personal data.

Output: redacted audit evidence and approval-required plan.

## Interfaces
- `Settings`
- `RedactionPolicy`
- `app/approval/service.py::ApprovalService`
- `app/approval/providers.py::ApprovalProvider`

## Implementation Notes
The MVP includes `.env.example` and avoids storing secrets in flow or user task files.

## Future Replacement Strategy
Add IAM, secret managers, encryption, and policy-as-code without changing domain contracts.
