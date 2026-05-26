# Architecture

## Purpose
Describe the end-to-end architecture for converting banking questions into explainable intent, event, plan, and task output.

## Responsibilities
- Preserve Clean Architecture boundaries.
- Apply Hexagonal Architecture with component-local provider adapters.
- Prevent AI components from executing business actions.
- Keep knowledge creation in ingestion and runtime answers as projections over validated flow knowledge.

## Main Components
- CLI/API entrypoints
- Application use cases
- Domain models and policies
- Component-local provider ports
- Infrastructure adapters for Neo4j, GraphRAG, LangGraph, LangChain, and OpenAI-compatible LLM APIs
- Flow answer context projection
- Central provider composition in `app/factory.py`

## Data Flow
Natural language enters a primary adapter. `AskService.resolve`
uses `AskState` and LangGraph `StateGraph` to orchestrate runtime nodes:
retrieval, classification, projection, approval, and audit. Query understanding
expands terms through the concept synonym catalog, GraphRAG retrieval reads
valid flows, user tasks, actions, concepts, and synonym aliases from
Neo4j, LangChain builds a restricted prompt, and the LLM selects one existing
flow or returns `unknown`. `AnswerBuilder` then projects the selected
flow's ingested business event, plan, tasks, related actions, and concepts
into the answer. Approval service marks approval required, audit service records
the result, and JSON is returned.

Ingestion follows a separate deterministic pipeline: raw corpus files are scanned and parsed by custom code, optionally analyzed by ingestion reasoning agents such as AutoGen-backed roles, normalized into flow/user-task/action JSON, validated by deterministic rules, written as preview or applied artifacts, audited, and loaded into Neo4j by a custom graph loader. This keeps expensive or exploratory agent reasoning on the knowledge-building side while runtime remains constrained to approved graph knowledge.

## Example Input/Output
Input: `Quiero bajar la cuota de mi prestamo`

Output: intent `loan.refinance`, event `LoanRefinancingRequested`, approval `true`.

## Interfaces
- Primary adapters: CLI and FastAPI routes.
- Input ports: `IngestKnowledgeUseCase`, `AskQuestionUseCase`.
- Output ports: graph, retrieval, reasoning, answer, capability registry, approval, audit.

## Implementation Notes
Dependencies point inward. Domain models know banking concepts, not framework types. Provider contracts live beside their component (`app/knowledge_graph/providers.py`, `app/ask/providers.py`, `app/capability/providers.py`), while `app/factory.py` wires the chosen implementations.

Runtime planning, task decomposition, business-event creation, and concept
creation should not happen during ask question. Those elements are created
during ingestion and projected by `app.ask.answer.AnswerBuilder`
after a `KnowledgeRecord` has been selected. Synonym aliases are normalized by
`app.knowledge_graph.vocabulary.ConceptVocabulary` during ingestion and reused by
question understanding. Ingestion reasoning operates before a `KnowledgeRecord`
exists and belongs under `app/ingestion`.

LangGraph is integrated in two places. Runtime ask uses `AskState` and a
compiled `StateGraph` for the question-answering sequence. Ingestion also has an
optional `LangGraphIngestionPipelineService` for conditional branches, retries,
or human-review state. Both workflows keep node bodies inside custom services
and provider ports.

## Future Replacement Strategy
Adapters may be swapped from GraphRAG to another retrieval strategy, LangChain to another prompt orchestration layer, OpenRouter/Groq/OpenAI to another OpenAI-compatible LLM provider, or Neo4j to another graph database by preserving input and output port contracts.
