# Banking Intent Platform Specifications

## Purpose
Define the MVP specifications for an Enterprise Banking Intent Engine and Knowledge Graph Platform.

For the product vision, full feature catalog, banking flow coverage, and user
stories with acceptance criteria, see
`docs/specs/system-vision-and-user-stories.md`.

For the runtime `ask` flow diagrams, including invoked classes and methods, see
`docs/specs/ask-sequence-diagrams.md`.

## Responsibilities
- Establish the target architecture and development order.
- Keep business logic independent from provider frameworks.
- Document how natural language becomes explainable planning output.

## Main Components
- Knowledge ingestion
- Deterministic ingestion pipeline
- LangGraph ingestion orchestration
- Ingestion reasoning
- Knowledge graph search
- Concept vocabulary
- Knowledge graph
- Ask flow selection
- Ask question trace
- Ask answer building
- Ingestion-time business event, planning, and task decomposition
- Fixed process definition artifacts
- Process execution orchestration
- Capability service
- Approval service
- Audit service

## Data Flow
Natural Language -> AskService -> Question Understanding -> KnowledgeGraphService Search -> Flow Selection -> AnswerBuilder -> Approval -> Audit -> Output JSON

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
- `app/ingestion/process_loader.py::ProcessDefinitionLoader`
- `app/orchestrator/process_execution.py::ProcessExecutionService`
- `app/knowledge_graph/providers.py::KnowledgeGraphRepository`
- `app/ask/providers.py::FlowSelectionProvider`
- `app/ask/answer.py::AnswerBuilder`
- `app/capability/providers.py::CapabilityProvider`
- `app/approval/providers.py::ApprovalProvider`
- `app/audit/providers.py::AuditSink`

## Implementation Notes
The operational path uses LangGraph ask orchestration, GraphRAG over Neo4j,
LangChain prompt orchestration, and an OpenAI-compatible LLM. The runtime ask
path requires those providers and does not resolve intent through a local
non-LLM path. Ingestion uses a
custom deterministic pipeline for scan, parse, validation, concept synonym
normalization, artifact writing, audit, and graph loading. AutoGen may provide
ingestion recommendations, but it does not own final JSON or Neo4j loading.
Runtime does not create plans, tasks, events, or concepts; it projects ingested
knowledge through `AnswerBuilder`. Each component keeps its own
service, provider protocol, and adapter under `app/<component>`.
`app/factory.py` wires runtime services together but does not own component
business logic.

## Future Replacement Strategy
Any provider can be replaced by implementing the corresponding component-local interface without changing domain services or CLI contracts.
