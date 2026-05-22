# Development Roadmap

## Purpose
Sequence MVP delivery while preserving replaceable architecture.

## Responsibilities
- Deliver specs first.
- Build flow-backed CLI.
- Add provider adapters incrementally.
- Expand graph and document ingestion.

## Main Components
- Phase 1: specs, structure, flows, user tasks, GraphRAG CLI ask path
- Phase 2: Neo4j adapter and graph loading
- Phase 3: action registry and flow/user-task JSON generation from corpus
- Phase 4: AutoGen ingestion reasoning for corpus review, flow design, task decomposition, action extraction, ontology linking, and validation
- Phase 5: GraphRAG retrieval over Neo4j
- Phase 6: LangChain constrained LLM reasoning with OpenAI-compatible providers
- Phase 7: FastAPI and enterprise security

## Data Flow
Each phase keeps the same natural-language-to-output JSON contract while improving providers behind interfaces.

## Example Input/Output
Phase 1 input: flow-backed Spanish question.

Phase 5 output: GraphRAG + LLM backed explainable response with audit and approval workflow integration.

## Interfaces
- Stable CLI and use case contracts
- Provider ports
- JSON output schema

## Implementation Notes
Do not introduce framework dependencies into domain services during later phases.

## Future Replacement Strategy
Roadmap milestones must preserve replacement options for AI, graph, vector, API, and storage frameworks.
