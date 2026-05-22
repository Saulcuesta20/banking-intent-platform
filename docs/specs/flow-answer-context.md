# Flow Answer Context

## Purpose
Project already-ingested flow knowledge into the runtime answer after an intent has been selected.

## Responsibilities
- Read the selected flow's `business_event`, `plan`, `tasks`, `capabilities`, and `ontology_nodes`.
- Rank ontology nodes lightly against the user question.
- Derive related front/back actions from the selected flow's user tasks.
- Avoid creating new plans, tasks, events, actions, or ontology during runtime.

## Main Components
- `app.flow_context.service.FlowAnswerContextService`
- `app.flow_context.service.FlowAnswerContext`
- `app.models.KnowledgeRecord`

## Data Flow
`IntentResolutionService` selects a `KnowledgeRecord` through retrieval and intent classification. `FlowAnswerContextService` then projects fields from that record into an answer context. Approval enforcement may add approval steps after projection, and the final `IntentResult` is returned.

## Runtime Boundary
Runtime does not create these elements:

| Element | Created during ingestion | Projected during ask question |
|---|---:|---:|
| Business event | Yes | Yes |
| Plan | Yes | Yes |
| User tasks | Yes | Yes |
| Front/back actions | Yes | Yes |
| Ontology nodes | Yes | Yes |

## Former Runtime Services
The older runtime services below are no longer wired into `app/factory.py`:

| Former service | Current runtime replacement |
|---|---|
| `BusinessEventService` | `FlowAnswerContextService.business_event` projection |
| `PlanningService` | `FlowAnswerContextService.plan` projection |
| `DecompositionService` | `FlowAnswerContextService.tasks` projection |
| `OntologyService` | `FlowAnswerContextService.related_ontology_nodes` ranking |

These packages were removed from the active code path so the runtime structure matches the architecture: plan/task/event/ontology are ingested knowledge, then projected during ask question.

## Implementation Notes
This component intentionally uses words like "project" and "read" instead of "create" or "decompose". Creation happens in ingestion through `IngestionPipelineService`, AutoGen recommendations, the LLM extractor, and deterministic validation.
