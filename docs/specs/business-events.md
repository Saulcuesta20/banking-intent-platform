# Business Events

## Purpose
Document where business events are created and how runtime projects them.

## Responsibilities
- Create stable event identifiers during ingestion.
- Store business events as governed business model knowledge and reference them from flow/process assets.
- Project the selected flow's event during ask question.
- Avoid publishing events to operational systems in the MVP.

## Main Components
- Ingestion extractor and validators
- `KnowledgeRecord.business_event`
- `AnswerBuilder`
- Event name conventions

## Data Flow
Ingestion creates or resolves a stable `business_event` for each flow/process.
During ask question, `AnswerBuilder` reads `record.business_event` from the
selected flow and includes it in the final `AnswerResult`.

## Example Input/Output
Input intent: `loan.refinance`

Output event: `LoanRefinancingRequested`.

## Interfaces
- `KnowledgeRecord.business_event`
- `AnswerBuilder.build(question, record)`

## Implementation Notes
Flow record currently carries the event value. In the owner-KB model, the
business model knowledge base should own the event catalog, while flow/process
assets reference event IDs. The old `BusinessEventService` runtime package was
removed from the active codebase; event projection now lives in `AnswerBuilder`.

## Future Replacement Strategy
Events can later align with enterprise event schemas or AsyncAPI catalogs during ingestion, then continue to be projected at runtime.
