# Banking Intent Platform

MVP for an Enterprise Banking Intent Engine and Knowledge Graph Platform.

The first implementation is flow-backed and framework-light. It preserves provider interfaces for AutoGen, LlamaIndex, Neo4j, GraphRAG, and future replacements while keeping banking decisions explainable and approval-gated.

Each application component owns its service and provider contract. Retrieval,
intent, flow context projection, graph, ingestion, capability, approval, and
audit all keep their logic inside their own `app/<component>`
package. `app/factory.py` is only the central composition root that chooses and
wires implementations.

## Architecture

Natural Language -> Knowledge Retrieval Service -> Intent Classification Service -> Flow Answer Context Service -> Approval Service -> Audit Service -> Output JSON

## Commands

Run from this directory:

```bash
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
make graph-load
make graph-tree FLOW=money.transfer DEPTH=3
make neo4j-stop
```

`make ask` uses GraphRAG over Neo4j plus LangChain prompt orchestration and an
LLM. Configure the key once with `make configure-ai KEY=...`; it writes `.env`,
which is ignored by git. The ask path does not have a local non-LLM resolver.

`make ask` prints the component trace by default. Use `--no-trace` only when
calling the CLI directly and you want just the result payload:

```bash
python -m app.cli ask "Quiero transferir dinero" --no-trace
```

## Flow Graph

Flow JSON files live in `data/flows`. Reusable user task JSON files live in
`data/user_tasks`. A flow is a business process composed of ordered
`user_task_refs`; each user task defines `front_actions` and `back_actions`.
Those actions are also matriculated into one derived repository:
`data/action_registry/actions.registry.json`.
When the service starts, `app/factory.py` rebuilds the live action registry from
the current flow and user task JSON files, so the runtime registry follows the
corpus-generated data.

Plans, user tasks, actions, business events, and ontology nodes are created
during ingestion. Runtime question answering selects a flow and projects those
validated fields with `FlowAnswerContextService`; it does not create or
decompose plans dynamically.

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

Add local role-based ingestion guidance when you want the extractor to follow
the same responsibilities as the AutoGen agents without running a multi-agent
chat:

```bash
OPENAI_API_KEY=... python tools/extract_flows_from_corpus.py --raw-dir data/raw --ingestion-reasoning
```

Run the real AutoGen ingestion agents when you want multi-agent review before
the final JSON extraction:

```bash
OPENAI_API_KEY=... python tools/extract_flows_from_corpus.py --raw-dir data/raw --autogen-ingestion-reasoning
```

The extraction command is coordinated by a deterministic pipeline. Custom code
scans/parses files, validates JSON, writes artifacts, and writes an audit record
under `data/processed/ingestion_audit`. AutoGen only contributes advisory
findings for the extractor.

Make shortcuts:

```bash
make extract
make extract-reasoning
make extract-autogen
make extract-langgraph
make extract-autogen-langgraph
make extract-apply
make extract-autogen-apply
```

The LangGraph extraction commands use the optional graph orchestrator for
retry/halt routing and human-review metadata. The custom pipeline remains the
default for simple linear extraction.

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
