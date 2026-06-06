# CLI Interface

## Purpose
Provide local commands for ingestion and question answering.

## Responsibilities
- Ingest knowledge from a path.
- Extract flow/user-task/tool artifacts from raw corpus files.
- Ask a natural-language business question.
- Run end-to-end ask scenario suites from YAML.
- Inspect, search, validate, and sync enterprise assets.
- Print component trace plus structured JSON, including graph retrieval and LLM decision details when enabled.
- Configure an OpenAI-compatible LLM provider for GraphRAG intent resolution.

## Main Components
- `app.cli.ingest`
- `app.cli.ask`
- `app.cli.ask-suite`
- `tools/extract_flows_from_corpus.py`
- `app.cli.assets-list`
- `app.cli.assets-show`
- `app.cli.assets-search`
- `app.cli.assets-validate`
- `app.cli.assets-sync`
- `app.cli.kb-views`
- `app.cli.kb-route`
- `app.cli.kb-search`
- `app.cli.kb-evidence`
- `app.cli.orchestrator-validate-definitions`
- `app.launcher_cli`
- `app.database_cli`
- Application service factory
- JSON output serializer

## Data Flow
The user runs a CLI command, the CLI calls a use case, and the result is printed as JSON.

## Example Input/Output
Input: `ask "Quiero refinanciar mi prestamo"`

Output: trace, `can_resolve`, intent, confidence, event, approval flag, plan,
tasks, tool capabilities, and entities currently exposed as concepts.

## Interfaces
- `IngestKnowledgeUseCase.execute(path)`
- `AskQuestionUseCase.execute(question)`

## Implementation Notes
Typer is the CLI framework, but command modules stay thin and framework-light. `ask` uses LangGraph + GraphRAG + Neo4j + LangChain + LLM. There is no non-LLM intent resolver for the ask path.

Corpus extraction uses the deterministic ingestion orchestrator in `app/ingestion/orchestrator.py`. `ingest` can enable role-based recommendations, but custom code still owns sequence, validation, artifact writing, and audit.

The optional LangGraph ingestion orchestrator can be enabled for retry/halt routing and human-review metadata.

The default ask output is compact. Use `--full-result` to print the full payload.
For question answering trace semantics, see `docs/specs/ask-question-trace.md`.
Use the trace output from `ask --debug-trace` to print the latest JSON trace file with graph and LLM details.

End-to-end ask scenario suites:

```bash
python -m app.cli ask-suite
python -m app.cli ask-suite --id tool_loan_conditions_explanation
python -m app.cli ask-suite --debug-trace
```

The default suite file is `e2e/ask_scenarios.yaml`. The command runs each
question through the real ask runtime, compares expected route decisions, and
writes a JSON report under `data/processed/e2e_runs`.

Enterprise asset commands:

```bash
kb query --engines
kb query --asset-type business_rule --text "automatic payment"
kb query --id business_rule.automatic_payment_account_required
kb query --text "pago automatico cuenta"
kb query --relation-type causes --format json
```

`assets-sync` currently writes `data/processed/asset_index/enterprise_assets.index.json`
as a neutral technical index of approved assets. Under the owner-KB model, the
next version should emit KB-oriented indexes. Those indexes can feed graph or
search infrastructure, but they do not turn graph/vector stores into the owner of an
asset.

Knowledge-base inspection commands:

```bash
kb query --engines
kb query --text "Como se aplica la regla de pago automatico en refinanciamiento?"
kb query --asset-type causality --text "mora"
kb query --asset-type plan --owner-kb planning_kb --text "cobranza preventiva"
kb query --owner-kb business_model_kb --asset-type entity --text "prestamo"
kb query --relation-type causes --format json
kb ingest --raw data/raw/enterprise_dump_2026
kb reset-ingest --raw data/raw/enterprise_dump_2026
```

`kb query` is now the preferred logical command for inspecting the knowledge-base
engine. It can filter by owner KB, asset type, relation type, and text while
still exposing the underlying technical stores. `kb ingest` and
`kb reset-ingest` run the asset-oriented ingestion path, which extracts
candidate assets from corpus, normalizes them, aligns them against the unified
catalog, and only then projects them to graph/document/vector stores.

Unclassified enterprise dump extraction:

```bash
ingest --raw data/raw/enterprise_dump_2026
ingest --raw data/raw/enterprise_dump_2026 --apply
kb query --engines
```

The dump lives under `data/raw/enterprise_dump_2026` and intentionally contains
mixed raw documents instead of preclassified assets. The ingestion orchestrator is
responsible for semantic classification, extraction, validation, audit, and
human-review artifacts before generated assets are applied.

Orchestrator definition validation:

```bash
python -m app.cli orchestrator-validate-definitions
```

Executable flow/process YAML definitions live in:

```text
config/definitions/flows/*.yaml
config/definitions/processes/*.yaml
```

Validation applies Python-side node policy by definition type (`flow` vs `process`)
before runtime execution.

## Future Replacement Strategy
FastAPI routes can call the same use cases as the CLI.
