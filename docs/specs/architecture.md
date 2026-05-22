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
- Infrastructure adapters for Neo4j, GraphRAG, LangChain, and OpenAI-compatible LLM APIs
- Flow answer context projection
- Central provider composition in `app/factory.py`

## Data Flow
Natural language enters a primary adapter, GraphRAG retrieval reads valid flows, user tasks, and actions from Neo4j, LangChain builds a restricted prompt, and the LLM selects one existing flow or returns `unknown`. `FlowAnswerContextService` then projects the selected flow's ingested business event, plan, tasks, related actions, and ontology nodes into the answer. Approval service marks approval required, audit service records the result, and JSON is returned.

Ingestion follows a separate deterministic pipeline: raw corpus files are scanned and parsed by custom code, optionally analyzed by ingestion reasoning agents such as AutoGen-backed roles, normalized into flow/user-task/action JSON, validated by deterministic rules, written as preview or applied artifacts, audited, and loaded into Neo4j by a custom graph loader. This keeps expensive or exploratory agent reasoning on the knowledge-building side while runtime remains constrained to approved graph knowledge.

## Example Input/Output
Input: `Quiero bajar la cuota de mi prestamo`

Output: intent `loan.refinance`, event `LoanRefinancingRequested`, approval `true`.

## Interfaces
- Primary adapters: CLI and FastAPI routes.
- Input ports: `IngestKnowledgeUseCase`, `AskQuestionUseCase`.
- Output ports: graph, retrieval, reasoning, flow context, capability registry, approval, audit.

## Implementation Notes
Dependencies point inward. Domain models know banking concepts, not framework types. Provider contracts live beside their component (`app/retrieval/providers.py`, `app/planning/providers.py`, `app/capability/providers.py`, etc.), while `app/factory.py` wires the chosen implementations.

Runtime planning, task decomposition, business-event creation, and ontology creation should not happen during ask question. Those elements are created during ingestion and projected by `app.flow_context.service.FlowAnswerContextService` after a `KnowledgeRecord` has been selected. Ingestion reasoning operates before a `KnowledgeRecord` exists and belongs under `app/ingestion`.

LangGraph is integrated as an optional ingestion workflow orchestrator through `LangGraphIngestionPipelineService`. Use it when conditional branches, retries, or human-review state are needed. The default implementation can still use `IngestionPipelineService` because the linear path is simpler and easier to audit as custom code.

## Future Replacement Strategy
Adapters may be swapped from GraphRAG to another retrieval strategy, LangChain to another prompt orchestration layer, OpenRouter/Groq/OpenAI to another OpenAI-compatible LLM provider, or Neo4j to another graph database by preserving input and output port contracts.
