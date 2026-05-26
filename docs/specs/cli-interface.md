# CLI Interface

## Purpose
Provide local commands for ingestion and question answering.

## Responsibilities
- Ingest knowledge from a path.
- Extract flow/user-task/action artifacts from raw corpus files.
- Ask a natural-language business question.
- Print component trace plus structured JSON, including graph retrieval and LLM decision details when enabled.
- Configure an OpenAI-compatible LLM provider for GraphRAG intent resolution.

## Main Components
- `app.cli.ingest`
- `app.cli.ask`
- `tools/extract_flows_from_corpus.py`
- `Makefile` service and provider commands
- Application service factory
- JSON output serializer

## Data Flow
The user runs a CLI command, the CLI calls a use case, and the result is printed as JSON.

## Example Input/Output
Input: `make ask Q="Quiero refinanciar mi prestamo"`

Output: trace, `can_resolve`, intent, confidence, event, approval flag, plan, tasks, action capabilities, and concepts.

## Interfaces
- `IngestKnowledgeUseCase.execute(path)`
- `AskQuestionUseCase.execute(question)`

## Implementation Notes
Typer is the CLI framework, but command modules stay thin and framework-light. `make ask` uses LangGraph + GraphRAG + Neo4j + LangChain + LLM. There is no non-LLM intent resolver for the ask path.

Corpus extraction uses the deterministic ingestion pipeline in `app/ingestion/pipeline.py`. `make extract-autogen` enables AutoGen recommendations, but custom code still owns sequence, validation, artifact writing, and audit.

`make extract-langgraph` and `make extract-autogen-langgraph` use the optional LangGraph ingestion orchestrator for retry/halt routing and human-review metadata.

The default ask output is compact. Use `--full-result` to print the full payload.
For question answering trace semantics, see `docs/specs/ask-question-trace.md`.
Use `make ask-trace-latest` to print the latest JSON trace file with graph and LLM details.

## Future Replacement Strategy
FastAPI routes can call the same use cases as the CLI.
