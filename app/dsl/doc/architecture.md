# DSL Architecture

## Purpose

Define a SQL-like authoring layer for enterprise assets without disturbing the
current repository-first architecture.

The DSL is an ingestion-time tool. It creates or updates knowledge assets,
compiles them into the existing repository format, and can also trigger a full
regeneration from corpus sources. It is not the runtime ask system.

## Why This Exists

We already have:

- an enterprise asset registry
- a repository-backed asset catalog
- a knowledge base runtime view
- ingestion that extracts flows from corpus
- validation and sync services
- an API boundary that a VS Code extension can call

The DSL should sit above those pieces and reuse them, not compete with them.

## Tech Stack

### Runtime And Platform

- Python 3.12
- FastAPI for the authoring API
- Pydantic for AST, validation, and compiled asset models
- Typer for CLI entrypoints if we expose local authoring commands
- SQLite for local catalog/index storage where needed
- Neo4j for graph projection and relationship retrieval
- Qdrant for semantic/vector projection when available
- Postgres for runtime or audit-oriented state
- JSON/YAML as the emitted repository artifact format

### Ingestion And Knowledge Creation

- current ingestion orchestrator in `app/ingestion/orchestrator.py`
- current corpus flow loader in `app/ingestion/llm_flow_loader.py`
- current asset registry and repository services
- current validation and sync services
- OpenAI-compatible LLM calls only where extraction is already expected

### Editor And Extension

- TypeScript for the VS Code extension
- VS Code Extension API for commands, tree view, diagnostics, and webviews
- Language Server Protocol for editor feedback
- Langium for grammar, parser, validation, and language tooling

### Optional Frontend Support

- Monaco or VS Code webview content only if we need richer previews
- JSON schema generation for machine-readable config and autocomplete support

## Reference Pattern

IBM business rule tooling is a useful mental model:

- rules are written in a business-friendly language
- decision tables are structured for analysts
- the authoring tool compiles to engine-ready artifacts
- the editor and the runtime are different layers

That is the pattern we want here.

Examples from IBM docs show that business rules can be written as
human-readable if-then statements, or in table form for multi-condition
decisions. We want a comparable experience for banking assets: readable,
declarative, and compilable.

## Layered Model

```text
DSL text
  -> parser
  -> AST
  -> validator
  -> asset compiler
  -> repository artifacts
  -> validation
  -> sync
  -> knowledge base indexing
  -> ask/runtime consumption
```

## Proposed Components

### Authoring Layer

The user writes SQL-like statements:

```text
CREATE KNOWLEDGE_BASE process_kb;
CREATE FLOW loan_refinance;
CREATE RULE refinance_eligibility;
CREATE PROCESS loan_refinance;
CREATE USER_TASK identify_customer;
CREATE TOOL customer.read;
CREATE ENTITY loan;
CREATE QA refinance_help;
```

### Parser And Validator

The parser turns text into an AST. The validator checks:

- asset ownership
- naming conventions
- relation validity
- lifecycle constraints
- execution constraints

### Compiler

The compiler converts the AST into the current asset model and repository
artifacts.

It must not create a second persistence path.

### Apply Layer

Apply should reuse current services:

- asset repository write path
- asset validation service
- asset sync service
- ingestion orchestrator

### VS Code Layer

The extension should provide:

- syntax highlighting
- completion
- diagnostics
- tree view of the asset dictionary
- command palette actions
- optional webview for diffs and previews

### API Layer

The authoring API should expose endpoints for:

- previewing parsed AST
- validating a DSL document
- applying a change set
- listing the asset dictionary
- showing generated artifacts
- triggering ingestion-backed regeneration

### Persistence And Projection Layer

The compiler should write to the existing asset repository and then reuse the
current sync/index flows so the rest of the platform continues to read from
known sources of truth.

## Folder Boundary

Keep the idea in a dedicated branch of the repo:

```text
app/dsl/
  doc/
  grammar/
  parser/
  compiler/
  validator/
  runtime/
```

The editor extension can live outside `app/` in its own package when the design
matures.

## Ingestion-Only Scope For Now

This proposal applies only to ingestion because that is where knowledge and
assets are created.

That means the first version should support:

- create asset
- update asset
- delete asset
- validate asset
- regenerate from corpus

It should not change ask-time retrieval or process execution semantics.

## Recommended Sequence

1. Define the DSL grammar.
2. Define the asset-specific statements.
3. Build the validator.
4. Build the compiler to current YAML/JSON artifacts.
5. Add API endpoints for apply and preview.
6. Build the VS Code extension.

## Component Map

| Layer | Component | Responsibility |
|---|---|---|
| Authoring | DSL text | Human-readable asset statements |
| Parsing | Grammar + parser | Convert text to AST |
| Validation | Validator | Enforce ownership, naming, and relation rules |
| Compilation | Compiler | Produce current asset model and repository artifacts |
| Application | Authoring service | Apply changes through existing services |
| Projection | Sync/index services | Update catalog, graph, and search projections |
| Runtime | Knowledge base and ask stack | Consume approved assets only |
| Editor | VS Code extension | Explore, validate, and apply DSL documents |

## Suggested Implementation Modules

```text
app/dsl/
  doc/
  models.py
  registry.py
  grammar/
  parser/
  validator/
  compiler/
  service.py
  api.py
  runtime/
```
