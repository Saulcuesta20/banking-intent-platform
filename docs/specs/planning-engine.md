# Planning Knowledge

## Purpose
Define how plans are created during ingestion and projected during ask question.

## Responsibilities
- Create flow plans from corpus evidence during ingestion.
- Keep plan steps as stable user task identifiers.
- Avoid free-form runtime planning for customer questions.
- Let approval policy append required approval steps at runtime.

## Main Components
- `app.ingestion.llm_flow_loader.CorpusFlowLoader`
- `app.ingestion.reasoning.AutoGenIngestionReasoningProvider`
- `KnowledgeRecord.plan`
- `FlowAnswerContextService`
- Human approval policy

## Data Flow
The ingestion pipeline extracts `plan` from corpus evidence and validates it with flow/user-task references. During ask question, the selected flow's `record.plan` is projected by `FlowAnswerContextService`. `ApprovalService` may append `approve_business_case`.

## Example Input/Output
Input flow: `loan.refinance`

Projected plan: `identify_customer`, `review_loan_status`, `review_refinance_options`, `prepare_refinance_request`, `approve_business_case`.

## Interfaces
- `KnowledgeRecord.plan`
- `FlowAnswerContextService.build(question, record)`

## Implementation Notes
The older `PlanningService` runtime package was removed from the active codebase. Runtime treats plans as ingested knowledge, not as newly generated output.

## Future Replacement Strategy
Planning generation can become richer inside ingestion by improving AutoGen roles, schema validation, or corpus extraction prompts. Runtime should continue to select and project validated plans.
