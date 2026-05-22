# Task Decomposition Knowledge

## Purpose
Define how flow plans are decomposed into reusable user tasks during ingestion and projected during ask question.

## Responsibilities
- Convert corpus-backed process steps into reusable `user_tasks` during ingestion.
- Attach `front_actions` and `back_actions` to user tasks.
- Keep runtime tasks descriptive and non-executing.
- Avoid decomposing plans dynamically during ask question.

## Main Components
- `TaskDecomposerAgent`
- `ActionExtractorAgent`
- `CorpusFlowLoader.normalize_and_validate`
- `KnowledgeRecord.tasks`
- `KnowledgeRecord.user_tasks`
- `FlowAnswerContextService`

## Data Flow
Ingestion extracts reusable user tasks and validates that flow `user_task_refs` exist. During ask question, `FlowAnswerContextService` reads the selected flow's tasks and action references. `ApprovalService` may append an approval task after projection.

## Example Input/Output
Input plan step: `review_refinance_options`

Projected task: `review_refinance_options` with back action `loan.conditions.calculate`.

## Interfaces
- `KnowledgeRecord.tasks`
- `KnowledgeRecord.user_tasks`
- `FlowAnswerContextService.build(question, record)`

## Implementation Notes
The older `DecompositionService` runtime package was removed from the active codebase. Decomposition happens during ingestion through AutoGen/LLM recommendations plus deterministic validation.

## Future Replacement Strategy
Task generation can move to richer ingestion-time AI or workflow extraction, but it must retain the same user task and action schema.
