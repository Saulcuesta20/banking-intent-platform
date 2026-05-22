# Business Events

## Purpose
Document where business events are created and how runtime projects them.

## Responsibilities
- Create stable event identifiers during ingestion.
- Store business events on flow JSON and Neo4j `Flow` nodes.
- Project the selected flow's event during ask question.
- Avoid publishing events to operational systems in the MVP.

## Main Components
- Ingestion extractor and validators
- `KnowledgeRecord.business_event`
- `FlowAnswerContextService`
- Event name conventions

## Data Flow
Ingestion creates `business_event` on each flow. During ask question, `FlowAnswerContextService` reads `record.business_event` from the selected flow and includes it in the final `IntentResult`.

## Example Input/Output
Input intent: `loan.refinance`

Output event: `LoanRefinancingRequested`.

## Interfaces
- `KnowledgeRecord.business_event`
- `FlowAnswerContextService.build(question, record)`

## Implementation Notes
Flow JSON defines the event catalog. The old `BusinessEventService` runtime package was removed from the active codebase; event projection now lives in `FlowAnswerContextService`.

## Future Replacement Strategy
Events can later align with enterprise event schemas or AsyncAPI catalogs during ingestion, then continue to be projected at runtime.
