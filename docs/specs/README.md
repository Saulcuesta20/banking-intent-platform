# Banking Intent Platform Specifications

## Purpose
Define the MVP specifications for an Enterprise Banking Intent Engine and Knowledge Graph Platform.

For the product vision, full feature catalog, banking flow coverage, and user
stories with acceptance criteria, see
`docs/specs/system-vision-and-user-stories.md`.

## Responsibilities
- Establish the target architecture and development order.
- Keep business logic independent from provider frameworks.
- Document how natural language becomes explainable planning output.

## Main Components
- Knowledge ingestion
- Deterministic ingestion pipeline
- LangGraph ingestion orchestration
- Ingestion reasoning
- Knowledge retrieval
- Ontology service
- Knowledge graph
- Intent resolution
- Ask question trace
- Flow answer context projection
- Ingestion-time business event, planning, and task decomposition
- Capability service
- Approval service
- Audit service

## Data Flow
Natural Language -> GraphRAG Retrieval Service -> Neo4j Knowledge Graph -> LangChain-Constrained Intent Classification -> Flow Answer Context Projection -> Approval Service -> Audit Service -> Output JSON

## Example Input/Output
Input: `Quiero refinanciar mi prestamo`

Output:
```json
{
  "intent": "loan.refinance",
  "confidence": 0.9,
  "business_event": "LoanRefinancingRequested",
  "requires_human_approval": true,
  "can_resolve": true
}
```

## Interfaces
- `app/ingestion/providers.py::KnowledgeIngestionProvider`
- `app/ingestion/pipeline.py::IngestionPipelineService`
- `app/ingestion/pipeline.py::LangGraphIngestionPipelineService`
- `app/ingestion/reasoning.py::IngestionReasoningProvider`
- `app/retrieval/providers.py::KnowledgeRetrievalProvider`
- `app/graph/providers.py::GraphRepository`
- `app/intent/providers.py::SemanticReasoningProvider`
- `app/flow_context/service.py::FlowAnswerContextService`
- `app/capability/providers.py::CapabilityProvider`
- `app/approval/providers.py::ApprovalProvider`
- `app/audit/providers.py::AuditSink`

## Implementation Notes
The operational path uses GraphRAG over Neo4j plus LangChain prompt orchestration and an OpenAI-compatible LLM. The deterministic local resolver remains available as an explicit fallback. Ingestion uses a custom deterministic pipeline for scan, parse, validation, artifact writing, audit, and graph loading. AutoGen may provide ingestion recommendations, but it does not own final JSON or Neo4j loading. Runtime does not create plans, tasks, events, or ontology; it projects ingested knowledge through `FlowAnswerContextService`. Each component keeps its own service, provider protocol, and local or AI adapter under `app/<component>`. `app/factory.py` wires runtime services together but does not own component business logic.

## Future Replacement Strategy
Any provider can be replaced by implementing the corresponding component-local interface without changing domain services or CLI contracts.
