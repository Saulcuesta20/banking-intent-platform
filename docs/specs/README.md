# Banking Intent Platform Specifications

## Purpose
Define the MVP specifications for an Enterprise Banking Intent Engine and Knowledge Base Platform.

For the product vision, full feature catalog, banking flow coverage, and user
stories with acceptance criteria, see
`docs/specs/system-vision-and-user-stories.md`.

For the runtime `ask` flow diagrams, including invoked classes and methods, see
`docs/specs/ask-sequence-diagrams.md`.

For the enterprise asset model, owner knowledge bases, asset routing, task/tool
boundaries, and YAML registry, see `docs/specs/enterprise-asset-registry.md`.

For the proposed agent abstraction over LangGraph, ingestion coordinator,
ask coordinator, and specialist asset agents, see
`docs/specs/agent-langgraph-architecture.md`.

For the Enterprise AI Launcher design, Lowdefy integration, component
breakdown, and tech stack, see `docs/launcher/README.md`.

For Python readability standards, dataclass usage, Pydantic boundaries, and
component style rules, see `docs/specs/python-code-standards.md`.

## Responsibilities
- Establish the target architecture and development order.
- Keep business logic independent from provider frameworks.
- Document how natural language becomes explainable planning output.

## Main Components
- Knowledge ingestion
- Knowledge base
- Deterministic ingestion orchestrator
- LangGraph ingestion orchestration
- Agent and LangGraph architecture
- Python code standards
- Extraction instructions
- Knowledge base search
- Entity vocabulary
- Knowledge-base graph adapter
- Ask flow selection
- Ask question trace
- Ask answer building
- Ingestion-time business event, planning, and task decomposition
- Fixed process definition artifacts
- Configurable enterprise asset registry
- Owner knowledge bases for processes, planning, rules, Q&A, business model, documents, and configuration
- Process execution orchestration
- Capability service
- Approval service
- Audit service

## Data Flow
Natural Language -> AskService -> Question Understanding -> KB/Index Search -> PlanningService -> Flow Selection -> AnswerBuilder -> Approval -> Audit -> Output JSON

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
- `app/ingestion/orchestrator.py::IngestionOrchestratorService`
- `app/ingestion/orchestrator.py::IngestionOrchestratorService`
- `app/ingestion/orchestrator.py::LangGraphIngestionOrchestratorService`
- `app/ingestion/orchestrator.py::ExtractionInstructionBuilder`
- `app/knowledge_base/repository.py::EnterpriseAssetRepository`
- `app/orchestrator/process_execution.py::OrchestrationExecutorService`
- `app/knowledge_base/ports.py::KnowledgeBaseRepository`
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
custom deterministic pipeline for scan, parse, validation, entity synonym
normalization, artifact writing, audit, and graph loading. Role-based ingestion
extraction instructions may provide recommendations, but it does not own final JSON or Neo4j
loading.
Runtime does not create plans, tasks, events, or entities; it projects ingested
knowledge through `AnswerBuilder`. Tasks are composed of tools, and
tools are the lowest approved capability level. Each component keeps its own
service, provider protocol, and adapter under `app/<component>`.
`app/factory.py` wires runtime services together but does not own component
business logic.

## Future Replacement Strategy
Any provider can be replaced by implementing the corresponding component-local interface without changing domain services or CLI contracts.
