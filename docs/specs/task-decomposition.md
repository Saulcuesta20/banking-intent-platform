# Task Decomposition Knowledge

## Purpose
Define how flow plans are decomposed into reusable user tasks during ingestion and projected during ask question.

## Responsibilities
- Convert corpus-backed process steps into reusable `user_tasks` during ingestion.
- Attach `tools` and `tools` to user tasks.
- Treat a user task as a reusable work unit, not the final execution primitive.
- Treat tools as the lowest approved capability level.
- Keep runtime tasks descriptive and non-executing.
- Avoid decomposing plans dynamically during ask question.

## Main Components
- `TaskDecomposerAgent`
- `ToolExtractorAgent`
- `CorpusFlowLoader.normalize_and_validate`
- `KnowledgeRecord.tasks`
- `KnowledgeRecord.user_tasks`
- `AnswerBuilder`

## Data Flow
Ingestion extracts reusable user tasks and validates that flow `user_task_refs`
exist. Each task owns an ordered or grouped list of tool references:

```text
user_task
  -> tools
  -> tools
```

During ask question, `AnswerBuilder` reads the selected flow's tasks and tool
references. `ApprovalService` may append an approval task after projection.

## Example Input/Output
Input plan step: `review_refinance_options`

Projected task: `review_refinance_options` with backend tool `loan.conditions.calculate`.

Example task boundary:

```text
user_task.review_refinance_options
  tools:
    - ui.refinance.calculate
  tools:
    - loan.conditions.calculate
    - loan_refinance.compare
```

`frontend_tool` represents a UI/channel interaction such as a click, submit,
upload, selection, or confirmation. `backend_tool` represents a backend
capability invocation through an approved protocol such as API, gRPC, MCP,
event, database, or manual adapter.

## Interfaces
- `KnowledgeRecord.tasks`
- `KnowledgeRecord.user_tasks`
- `AnswerBuilder.build(question, record)`

## Implementation Notes
The older `DecompositionService` runtime package was removed from the active
codebase. Decomposition happens during ingestion through role-based/LLM
recommendations plus deterministic validation. Processes and flows may compose
tasks and tools by reference, but the reusable definitions belong to the
business model knowledge base.

## Future Replacement Strategy
Task generation can move to richer ingestion-time AI or workflow extraction, but it must retain the same user task and tool schema.
