# Intent Resolution

## Purpose
Detect the banking intent behind a user question.

## Responsibilities
- Combine semantic reasoning, retrieved knowledge, and ontology matches.
- Return confidence and explanation evidence.
- Avoid executing or triggering banking actions.
- Project selected flow knowledge instead of creating runtime plans, tasks, events, or ontology.

## Main Components
- `IntentResolutionService`
- `IntentClassificationService`
- `app/intent/providers.py::SemanticReasoningProvider`
- `app/intent/local.py`
- `app/intent/ai.py`
- `app/flow_context/service.py::FlowAnswerContextService`
- Intent candidate model
- Confidence policy

## Data Flow
Question text and retrieved flow context are passed to `IntentClassificationService`. In local mode, the best local candidate is selected deterministically. In AI mode, GraphRAG retrieval reads valid flows, user tasks, and actions from Neo4j; LangChain builds the constrained prompt; the LLM must either choose one existing flow id or return `unknown`. The selected flow is then passed to `FlowAnswerContextService`, which reads the ingested business event, plan, tasks, actions, and ontology nodes for the final response.

## Example Input/Output
Input: `Quiero refinanciar mi prestamo`

Output: `loan.refinance` with confidence `0.90`.

## Interfaces
- `IntentResolutionService.resolve(question)`
- `IntentClassificationService.classify(question, records)`
- `SemanticReasoningProvider.classify_intent(question, records)`

## Implementation Notes
The default `make ask` path uses GraphRAG reasoning in `app/retrieval/graph.py` and `app/intent/ai.py`. Local flow utterance matching in `app/intent/local.py` remains available through the deterministic fallback. Runtime flow context is a projection over ingested knowledge; plan and user-task creation live in ingestion.

## Future Replacement Strategy
LangChain, AutoGen, or another reasoning provider can be replaced as long as it returns one valid existing flow or no match.
