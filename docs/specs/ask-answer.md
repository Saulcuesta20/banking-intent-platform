# Ask Answer

## Purpose
Project already-ingested flow knowledge into the runtime answer after an intent has been selected.

## Responsibilities
- Read the selected flow's `business_event`, `plan`, `tasks`, `capabilities`, and `concepts`.
- Rank concepts lightly against the user question.
- Derive related front/back actions from the selected flow's user tasks.
- Avoid creating new plans, tasks, events, actions, or concepts during runtime.

## Main Components
- `app.ask.answer.AnswerBuilder`
- `app.ask.answer.AnswerContext`
- `app.models.FlowDefinition` (`KnowledgeRecord` remains as a compatibility alias)

## Data Flow
`AskService` selects a `KnowledgeRecord` through knowledge graph search and flow selection. `AnswerBuilder` then projects fields from that record into an answer context. Approval enforcement may add approval steps after projection, and the final `AnswerResult` is returned.

## Runtime Boundary
Runtime does not create these elements:

| Element | Created during ingestion | Projected during ask question |
|---|---:|---:|
| Business event | Yes | Yes |
| Plan | Yes | Yes |
| User tasks | Yes | Yes |
| Front/back actions | Yes | Yes |
| Concepts | Yes | Yes |

## Former Runtime Services
The older runtime services below are no longer wired into `app/factory.py`:

| Former service | Current runtime replacement |
|---|---|
| `BusinessEventService` | `AnswerBuilder.business_event` projection |
| `PlanningService` | `AnswerBuilder.plan` projection |
| `DecompositionService` | `AnswerBuilder.tasks` projection |
| `ConceptService` | `AnswerBuilder.related_concepts` ranking |

These packages were removed from the active code path so the runtime structure matches the architecture: plan/task/event/concept are ingested knowledge, then projected during ask question.

## Implementation Notes
This component intentionally uses words like "project" and "read" instead of "create" or "decompose". Creation happens in ingestion through `IngestionPipelineService`, AutoGen recommendations, the LLM extractor, and deterministic validation.
