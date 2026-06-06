# Ask Flow Selection

## Purpose
Detect the banking intent behind a user question.

## Responsibilities
- Combine semantic reasoning, retrieved knowledge, and entity/synonym matches.
- Return confidence and explanation evidence.
- Avoid executing or triggering banking tools.
- Project selected flow knowledge instead of creating runtime plans, tasks, events, or entities.

## Main Components
- `AskService`
- `FlowSelectionService`
- `app/ask/providers.py::FlowSelectionProvider`
- `app/ask/ai.py`
- `app/ask/answer.py::AnswerBuilder`
- Intent candidate model
- Confidence policy

## Data Flow
Question text and retrieved answer are passed to `FlowSelectionService`.
GraphRAG retrieval reads valid flows, user tasks, tools, entities, and
synonyms from Neo4j; LangChain builds the constrained prompt; the LLM must
either choose one existing flow id or return `unknown`. The selected flow is
then passed to `AnswerBuilder`, which reads the ingested business event, plan,
tasks, tools, and entity values currently stored as `concepts` for the final
response.

## Example Input/Output
Input: `Quiero refinanciar mi prestamo`

Output: `loan.refinance` with confidence `0.90`.

## Interfaces
- `AskService.resolve(question)`
- `FlowSelectionService.select(question, records)`
- `FlowSelectionProvider.select_intent(question, records)`

## Implementation Notes
The default `ask` path uses GraphRAG reasoning in
`app/knowledge_base/adapters/graph/neo4j.py` and `app/ask/ai.py`. Runtime answer
is a projection over ingested knowledge; plan and user-task creation live in
ingestion. If the LLM, LangGraph, or Neo4j path is unavailable, ask fails with a
configuration error instead of choosing a local non-LLM intent.

## Future Replacement Strategy
LangChain, LangGraph, or another reasoning provider can be replaced as long as it returns one valid existing flow or no match.
