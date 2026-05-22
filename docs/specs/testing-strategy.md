# Testing Strategy

## Purpose
Validate the platform behavior and architectural boundaries.

## Responsibilities
- Test deterministic intent resolution.
- Test flow and user task ingestion.
- Test human approval enforcement.
- Test provider interfaces with fakes.
- Test GraphRAG prompt boundaries with fake LLM clients.

## Main Components
- Unit tests for services
- CLI smoke tests
- Provider contract tests
- Future integration tests for Neo4j and OpenAI-compatible LLM providers

## Data Flow
Tests load flow records and resolved user tasks, call use cases, and assert structured output.

## Example Input/Output
Input test: ask `Quiero refinanciar mi prestamo`

Expected output: intent `loan.refinance`, event `LoanRefinancingRequested`, approval `true`.

## Interfaces
- `pytest`
- Provider fakes
- CLI module entrypoints

## Implementation Notes
Unit tests default to deterministic mode so they do not require network, Neo4j, or LLM quota. GraphRAG/LLM behavior should be covered with fakes and optional integration tests.

## Future Replacement Strategy
Add Testcontainers or Docker Compose integration tests for Neo4j and provider-specific adapters such as OpenRouter, Groq, and OpenAI.
