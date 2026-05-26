# Ask Flow Selection

## Purpose
Detect the banking intent behind a user question.

## Responsibilities
- Combine semantic reasoning, retrieved knowledge, and concept matches.
- Return confidence and explanation evidence.
- Avoid executing or triggering banking actions.
- Project selected flow knowledge instead of creating runtime plans, tasks, events, or concepts.

## Main Components
- `AskService`
- `FlowSelectionService`
- `app/ask/providers.py::FlowSelectionProvider`
- `app/ask/ai.py`
- `app/ask/answer.py::AnswerBuilder`
- Intent candidate model
- Confidence policy

## Data Flow
Question text and retrieved answer are passed to `FlowSelectionService`. GraphRAG retrieval reads valid flows, user tasks, and actions from Neo4j; LangChain builds the constrained prompt; the LLM must either choose one existing flow id or return `unknown`. The selected flow is then passed to `AnswerBuilder`, which reads the ingested business event, plan, tasks, actions, and concepts for the final response.

## Example Input/Output
Input: `Quiero refinanciar mi prestamo`

Output: `loan.refinance` with confidence `0.90`.

## Interfaces
- `AskService.resolve(question)`
- `FlowSelectionService.select(question, records)`
- `FlowSelectionProvider.select_intent(question, records)`

## Implementation Notes
The default `make ask` path uses GraphRAG reasoning in `app/knowledge_graph/neo4j.py` and `app/ask/ai.py`. Runtime answer is a projection over ingested knowledge; plan and user-task creation live in ingestion. If the LLM, LangGraph, or Neo4j path is unavailable, ask fails with a configuration error instead of choosing a local non-LLM intent.

## Future Replacement Strategy
LangChain, AutoGen, or another reasoning provider can be replaced as long as it returns one valid existing flow or no match.
