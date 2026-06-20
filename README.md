# Banking Intent Platform

MVP for an Enterprise Banking Intent Engine and Knowledge Base Platform.

The first implementation is flow-backed and framework-light. It preserves provider interfaces for LlamaIndex, Neo4j, GraphRAG, LangGraph, and future replacements while keeping banking decisions explainable and approval-gated.

Each application component owns its service and provider contract.
`knowledge_base` owns governed enterprise knowledge, entity vocabulary, asset
search, and storage adapters. Neo4j is now a graph adapter under
`app/knowledge_base/adapters/graph`, not the component boundary. `ask` owns
question understanding, flow selection and answer building; ingestion,
capability, approval, and audit all keep their logic inside their own
`app/<component>` package. `app/factory.py` is only the central composition root
that chooses and wires implementations.

## Architecture

Natural Language -> Ask Service -> Question Understanding -> Knowledge Base Search -> Flow Selection -> Answer Builder -> Approval -> Audit -> Output JSON

## Commands

Run from this directory:

```bash
# Requires Neo4j because ingestion persists through the graph adapter:
python -m app.cli.ingest ./data/raw

# Start the API server:
python -m app.cli serve

# Ask always requires LLM + GraphRAG + Neo4j:
python -m app.cli ask "Quiero refinanciar mi prestamo"
```

Neo4j helper commands:

```bash
make neo4j-up
make neo4j-ps
make app-up
make configure-ai KEY=sk-your-real-key
# Or enter it hidden so it does not stay in shell history:
make configure-ai-prompt
# Or enter it hidden, save it, and validate it against OpenAI:
make configure-ai-check
# Or pass it inline; this may remain in shell history:
make configure-ai-inline KEY='sk-your-real-key'
# OpenRouter, useful for free remote models:
make configure-ai-inline PROVIDER=openrouter KEY='your-openrouter-key' MODEL='openrouter/auto'
# Groq, useful for fast hosted open models:
make configure-ai-inline PROVIDER=groq KEY='your-groq-key' MODEL='llama-3.3-70b-versatile'
make ask Q="Quiero transferir dinero"
make ask-suite
make ask-suite-one ID=tool_loan_conditions_explanation
make ask-multiple-intentions
make ask-tool
make assets-search Q="pago automatico cuenta"
make kb-views
make kb-route Q="Como calculan las condiciones de mi prestamo?"
make kb-search-repo Q="pago automatico cuenta"
make kb-search-graph Q="refinanciar prestamo"
make kb-evidence Q="Quiero refinanciar mi prestamo"
make assets-validate
make assets-sync
make orchestrator-assets
make orchestrator-instances
make graph-load
make graph-tree FLOW=money.transfer DEPTH=3
make neo4j-stop
```

`make ask` uses GraphRAG over the Neo4j knowledge-base graph adapter plus LangChain prompt orchestration and an
LLM. Configure the key once with `make configure-ai KEY=...`; it writes `.env`,
which is ignored by git. The ask path does not have a local non-LLM resolver.

`make ask` prints the component trace by default. Use `--no-trace` only when
calling the CLI directly and you want just the result payload:

```bash
python -m app.cli ask "Quiero transferir dinero" --no-trace
```

Inspect the latest JSON trace, including goal routing and multiple intentions planning:

```bash
make ask-trace-latest
make ask-suite-trace-latest
```

Run the end-to-end ask scenario suite to compare expected routes with actual
runtime decisions:

```bash
make ask-suite
make ask-suite-one ID=multiple_intentions_refinance_tool_qa
```

Scenarios live in `e2e/ask_scenarios.yaml`. Each run writes a report under
`data/processed/e2e_runs` with question understanding, goal route, knowledge
sources, evidence bundle, result, checks, and raw trace events.

Inspect orchestrator assets and active instances:

```bash
make orchestrator-assets
make orchestrator-execute FLOW=money.transfer DATA='{"customer_id":"C-123"}'
make orchestrator-instances
```

Inspect enterprise assets:

```bash
make assets-list
make assets-list TYPE=business_rule
make assets-show ID=business_rule.automatic_payment_account_required
make assets-search Q="pago automatico cuenta"
make assets-validate
make assets-sync
```

Inspect knowledge-base views and retrieval decisions:

```bash
kb query --engines
kb query --text "Como calculan las condiciones de mi prestamo?"
kb query --asset-type entity --owner-kb business_model_kb --text "prestamo"
kb query --asset-type plan --owner-kb planning_kb --text "cobranza preventiva"
kb query --asset-type causality --relation-type has_effect --text "mora"
make kb-evidence Q="Quiero refinanciar mi prestamo"
```

Repository queries run locally. Graph/evidence queries use Neo4j, so load the
graph first when needed:

```bash
make graph-load
```

## Flow Graph

Flow YAML files live in `data/flows`. Reusable user task YAML files live in
`data/user_tasks`. A flow is a business process composed of ordered
`user_task_refs`; each user task defines canonical `tools`.
Those tools are also registered into one derived configuration catalog:
`config/tool_registry/tools.registry.yaml`.
When the service starts, `app/factory.py` rebuilds the live tool registry from
the current flow and user task YAML files, so the runtime registry follows the
corpus-generated data.

Plans, user tasks, tools, business events, and entities are created
during ingestion. Runtime question answering selects a flow and projects those
validated fields with `AnswerBuilder`.

The ask path also writes a goal-routing trace. `PlanningService` detects the
customer goal, `user_needs`, each `resolution_action`, the route mode, and a
multiple intentions plan when the question combines multiple needs. Multiple
intentions planning only composes approved flows, processes, user tasks, and
registered tools; it does not invent banking tools.

Enterprise asset type configuration lives under `config/asset_registry`.
Approved business assets live under `data/qa`, `data/rules`, and `data/plans`.
`AskService` searches those assets during
`search_knowledge`, writes `asset_search` to the trace, and passes those results
to `PlanningService`. Business rules can also gate process execution before
tools are invoked.

## Configuration-Driven Models

Extraction schemas and runtime node definitions are now declared in YAML under `config/model`.
`config/model/extraction_schema.yaml` defines the LLM extraction JSON schema for flows, user tasks, and candidate business assets.
`config/model/node_types.yaml` defines allowed execution node types for `process` and `flow` definitions.
This keeps the runtime engine typed and declarative while moving prompt schema and policy definitions out of code.

```bash
OPENAI_API_KEY=... python tools/extract_flows_from_corpus.py --raw-dir data/raw --apply --clean
python tools/push_flows_to_neo4j.py --clear
python tools/neo4j_tree.py --source loan.refinance --depth 3
```

To extract flows and user tasks from any supported corpus folder using an LLM:

```bash
OPENAI_API_KEY=... python tools/extract_flows_from_corpus.py --raw-dir data/raw

# After reviewing data/generated:
OPENAI_API_KEY=... python tools/extract_flows_from_corpus.py --raw-dir data/raw --apply --clean
python tools/push_flows_to_neo4j.py --clear
```

To simulate a real company handoff, use the unclassified raw dump under
`data/raw/enterprise_dump_2026`. It contains mixed notes, HTML, CSV, JSON,
YAML, policy text, support tickets, and process fragments. The extraction step
must classify and propose candidate artifacts from that raw material:

```bash
kb ingest --raw data/raw/enterprise_dump_2026

# Reload everything from cero:
kb reset-ingest --raw data/raw/enterprise_dump_2026
```

Add local role-based ingestion guidance when you want the extractor to follow
the enterprise ingestion roles before generating reviewable artifacts:

```bash
OPENAI_API_KEY=... python tools/extract_flows_from_corpus.py --raw-dir data/raw --ingestion-reasoning
```

The extraction command is coordinated by an asset-oriented pipeline. Custom code
scans/parses files, validates JSON, expands candidates into entities, rules,
processes, flows, plans, causalities, Q&A, tools, and documents, normalizes
those assets against the unified `asset_catalog`, and only then writes graph,
document, and vector projections plus an audit record under
`data/processed/ingestion_audit`. Role-based reasoning contributes advisory
findings for the extractor. The application ingestion provider invokes
`KnowledgeBaseService` to persist approved records through the configured
knowledge-base adapter.

Make shortcuts:

```bash
make extract
make extract-reasoning
make extract-langgraph
make extract-apply
```

The LangGraph extraction commands use the optional graph orchestrator for
retry/halt routing and human-review metadata. The custom pipeline remains the
default for simple linear extrtool.

The LLM extractor discovers files dynamically from the folder passed in
`--raw-dir`. It supports text-like files (`.txt`, `.md`, `.csv`, `.json`,
`.yaml`, `.bpmn`, `.docx`), PDFs, and image files (`.png`, `.jpg`, `.jpeg`, `.webp`,
`.gif`, `.bmp`, `.tif`, `.tiff`). For PDFs it uses `pdftotext` when available;
if the PDF appears scanned, it can render the first pages with `pdftoppm` and
send them to the vision-capable LLM.

## Safety Rules

- No direct banking execution.
- Human approval is always required.
- AI reasoning only plans and explains.
- Providers are replaceable behind component-local interfaces.

## Specs

Design documents live in `docs/specs`.
