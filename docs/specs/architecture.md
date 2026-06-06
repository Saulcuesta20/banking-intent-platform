# Architecture

## Purpose
Describe the end-to-end architecture for converting banking questions into explainable intent, event, plan, and task output.

## Responsibilities
- Preserve Clean Architecture boundaries.
- Apply Hexagonal Architecture with component-local provider adapters.
- Prevent AI components from executing business tools.
- Keep knowledge creation in ingestion and runtime answers as projections over validated flow knowledge.

## Main Components
- CLI/API entrypoints
- Application use cases
- Domain models and policies
- Component-local provider ports
- Launcher presentation shell powered by Lowdefy
- Infrastructure adapters for Neo4j, GraphRAG, LangGraph, LangChain, and OpenAI-compatible LLM APIs
- Governed owner knowledge bases for processes, planning, rules, Q&A, business model, documents, and configuration
- Flow answer context projection
- Central provider composition in `app/factory.py`

## Data Flow
Natural language enters a primary adapter. `AskService.resolve`
uses `AskState` and LangGraph `StateGraph` to orchestrate runtime nodes:
retrieval, asset search, goal planning, classification, projection, approval,
and audit. Query understanding expands terms through the entity synonym
catalog. Retrieval uses owner knowledge bases and technical indexes: the current
GraphRAG path reads valid flows, user tasks, tools, entities, and synonym
aliases from Neo4j, while `AssetSearchService` reads approved enterprise assets
from the configured repositories. `PlanningService` produces the
goal/user-needs/route trace, LangChain builds a restricted prompt, and the LLM
selects one existing flow or returns `unknown`. `AnswerBuilder` then projects
the selected flow's ingested business event, plan, tasks, related tools, and
entities into the answer. Approval service marks approval required, audit
service records the result, and JSON is returned.

Ingestion follows a separate deterministic pipeline: raw corpus files are
scanned and parsed by custom code, optionally analyzed by role-based ingestion
reasoning, normalized into approved asset JSON/YAML, assigned to one owner KB,
validated by deterministic rules, written as preview or applied artifacts,
audited, and loaded into technical indexes such as Neo4j by custom loaders.
This keeps expensive or exploratory reasoning on the knowledge-building side
while runtime remains constrained to approved knowledge.

The proposed launcher sits above the platform as a config-driven presentation
layer. Lowdefy receives launcher page configuration, flow catalog data, and
run-time trace data from API endpoints, then renders cards, forms, tables,
logs, and master-detail views. The launcher does not own business workflow
logic; it translates YAML-defined flow and process metadata into UI blocks and
actions, and delegates execution back to the platform services.

## Example Input/Output
Input: `Quiero bajar la cuota de mi prestamo`

Output: intent `loan.refinance`, event `LoanRefinancingRequested`, approval `true`.

## Interfaces
- Primary adapters: CLI and FastAPI routes.
- Input ports: `IngestKnowledgeUseCase`, `AskQuestionUseCase`.
- Output ports: graph, retrieval, reasoning, answer, capability registry, approval, audit.

## Implementation Notes
Dependencies point inward. Domain models know banking entities, not framework
types. Provider contracts live beside their component
(`app/knowledge_base/ports.py`, `app/ask/providers.py`,
`app/capability/providers.py`), while `app/factory.py` wires the chosen
implementations.

Runtime planning, task decomposition, business-event creation, tool creation,
and entity creation should not happen during ask question.
Those elements are created during ingestion, assigned to their owner KB, and
projected by `app.ask.answer.AnswerBuilder` after a `KnowledgeRecord` has been
selected. Synonym aliases are currently normalized by
`app.knowledge_base.vocabulary.ConceptVocabulary` during ingestion and reused
by question understanding; this is the current compatibility name for entity
vocabulary. Extraction instructions operates before a
`KnowledgeRecord` exists and belongs under `app/ingestion`.

Processes and flows compose reusable pieces by reference:

```text
process/flow -> task -> frontend_tool/backend_tool
process/flow -> business_event
process/flow -> business_rule
process/flow -> plan
process/flow -> entity
```

Tasks and tools are owned by the business model KB. A frontend tool represents
a UI or channel intertool. A backend tool represents a backend capability
invocation through an approved adapter or protocol. Tools are the lowest
capability level that may be invoked after confirmation.

Launcher-specific UI rules:
- Flow YAML is source-of-truth for flow browsing and launch screens.
- Lowdefy pages map flow/process/user-task metadata to blocks, forms, and lists.
- Live trace and log panels are read-only projections of execution state.
- When a richer canvas is needed, it should be a custom Lowdefy plugin or a companion block, not inline business logic.

LangGraph is integrated in three places. Runtime ask uses `AskState` and a
compiled `StateGraph` for the question-answering sequence. Process execution
uses the orchestrator package as the workflow adapter that compiles and invokes
a LangGraph `StateGraph` over executable process nodes. Before process nodes
run, approved `business_rule` assets can gate execution by requiring missing
data. Ingestion also has an
optional `LangGraphIngestionOrchestratorService` for conditional branches, retries,
or human-review state. These workflows keep node bodies inside custom services
and provider ports.

## Future Replacement Strategy
Adapters may be swapped from GraphRAG to another retrieval strategy, LangChain to another prompt orchestration layer, OpenRouter/Groq/OpenAI to another OpenAI-compatible LLM provider, or Neo4j to another graph database by preserving input and output port contracts.

The launcher shell may also be swapped from Lowdefy to another config-driven UI framework if the launcher keeps the same page-data contract and flow catalog APIs.
