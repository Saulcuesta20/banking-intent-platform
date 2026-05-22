# Provider Abstraction

## Purpose
Define replaceable component-local interfaces for every application component.

## Responsibilities
- Keep domain services independent from frameworks.
- Make provider behavior testable with fakes.
- Allow LlamaIndex, AutoGen, Neo4j, GraphRAG, LangGraph, and other tools to be swapped.

## Main Components
- Component-local provider protocols
- Component-local adapter implementations
- Configuration factory
- Test doubles

## Data Flow
Application services call provider ports owned by their component. Provider adapters translate to external framework APIs and return domain objects.

## Example Input/Output
Input: `SemanticReasoningProvider.classify_intent(question, records)`

Output: intent candidates with confidence, explanation, and evidence.

## Interfaces
- `app/ingestion/providers.py::KnowledgeIngestionProvider`
- `app/ingestion/pipeline.py::IngestionPipelineService`
- `app/ingestion/reasoning.py::IngestionReasoningProvider`
- `app/retrieval/providers.py::KnowledgeRetrievalProvider`
- `app/intent/providers.py::SemanticReasoningProvider`
- `app/flow_context/service.py::FlowAnswerContextService`
- `app/graph/providers.py::GraphRepository`
- `app/capability/providers.py::CapabilityProvider`
- `app/approval/providers.py::ApprovalProvider`
- `app/audit/providers.py::AuditSink`

## Implementation Notes
Provider modules must not leak framework objects into domain packages.

Provider modules live inside the component they implement. For example, capability providers live under `app/capability`, graph providers live under `app/graph`, and runtime flow projection lives under `app/flow_context`.

Each component follows the same shape when useful:
- `service.py` owns orchestration logic for that component.
- `providers.py` defines the replaceable protocol.
- `local.py` contains deterministic local behavior.
- `ai.py` contains optional AI-backed behavior when that component needs it.

For GraphRAG intent resolution, `app/intent/service.py` owns the LangGraph
`AskState` workflow, `app/retrieval/graph.py` owns Neo4j retrieval,
`app/ontology/service.py` owns deterministic term normalization and synonym
aliases, and `app/intent/ai.py` owns LangChain prompt orchestration plus LLM
classification. The LLM receives only graph-derived candidate flows/actions and
must not invent new tasks.

## Future Replacement Strategy
Add a new adapter inside the owning component, bind it in `app/factory.py`, and leave use cases unchanged.
