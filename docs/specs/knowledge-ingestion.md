# Knowledge Ingestion

## Purpose
Load external banking knowledge from raw documents into governed enterprise
assets with one owner knowledge base per asset type.

## Responsibilities
- Accept PDF, Markdown, HTML, wiki pages, JSON, OpenAPI/Swagger, BPMN, and raw domain notes.
- Extract flows, processes, rules, Q&A, plans, entities, user tasks,
  tools, business events, documents, causalities, and cross-KB references.
- Detect candidate runtime intent classes from unlabeled enterprise text.
- Create flow plans and decompose them into reusable user tasks during ingestion.
- Build a single tool registry from all discovered `tools` and `tools`.
- Persist processed metadata and KB-oriented indexes for graph/search loading.
- Canonicalize assets before graph projection so aliases and duplicates collapse
  into one governed identity in the unified catalog.

## Main Components
- File source scanner
- Document parser registry
- Deterministic ingestion orchestrator service
- Extraction instructions service
- Semantic analyzer and classifier
- Role-based extraction instructions provider
- LLM-assisted corpus extractor
- Asset-oriented candidate extractor
- Relation detector backed by configured relation patterns
- Canonical normalizer and alignment service
- `IngestionOrchestratorService`
- `IngestionOrchestratorService`
- User task catalog loader
- Tool registry builder
- Processed artifact writer

## Data Flow
Raw files are scanned and parsed by deterministic code, classified by semantic
analysis, optionally analyzed by extraction instructions agents, extracted into
asset candidates, enriched with relation-family hints, normalized into
canonical assets, aligned against `asset_catalog`, validated by deterministic
schema rules, assigned to one owner knowledge base, written as preview or
applied artifacts, registered as tools when applicable, and recorded in
processed metadata plus ingestion audit and optional human-review records.

The asset-oriented phases are:

```text
scan corpus
  -> candidate extraction
  -> relation detection
  -> asset type resolution
  -> canonical normalization
  -> alignment against asset_catalog
  -> projection to catalog/document/graph/vector stores
```

Ownership assignment is part of ingestion:

```text
flow/process/process_node      -> process_kb
plan/plan_step                 -> planning_kb
business_rule                  -> rules_kb
qa                             -> qa_kb
entity/user_task/tool/business_event
                               -> business_model_kb
document                       -> document_kb
causality                      -> causality_kb
asset registry/validators      -> config_kb
```

The ingestion orchestrator may create technical search indexes, but those indexes
do not own assets. The owner KB remains the source of truth.

## Example Input/Output
Input: `Neo4j/loan_refinance.flow.yaml`

Output: approved assets assigned to owner KBs, reusable user tasks, resolved
tools, entities, business events, rules, Q&A, plans, causalities, and a
derived tool registry.

## Interfaces
- `app/ingestion/orchestrator.py::IngestionOrchestratorService.ingest(path)`
- `app/ingestion/orchestrator.py::IngestionOrchestratorService.run(config)`
- `DocumentParser.parse(path)`
- processed artifact writer in `app/ingestion/orchestrator.py`

## Implementation Notes
MVP ingestion still starts with flow and user task extraction through
`app/ingestion/orchestrator.py`, records file metadata and a tool registry in
processed output, and delegates approved graph persistence to
`app.knowledge_base.service.KnowledgeBaseService`. The KB ingestion path now
passes those records through `app/ingestion/asset_pipeline.py`, which expands
the run into asset-oriented candidate extraction, relation-family detection,
canonical naming, alignment against the unified catalog, and causality
extraction. The current direction is LLM-first for asset proposal generation:
the same OpenAI-compatible client used for flow extraction also proposes
entities, rules, processes, plans, Q&A, and causalities. Local code then
reconciles, validates, deduplicates, and projects those proposals. LLM-assisted corpus extraction lives in
`app/ingestion/llm_flow_loader.py`. The extraction command is coordinated by
`app/ingestion/orchestrator.py` and `tools/kb_reset_load.py`, which own
sequencing and audit.

Extraction instructions belongs in ingestion, not runtime planning.
`app/ingestion/orchestrator.py` defines a provider interface backed by
`RoleBasedExtractionInstructionBuilder`. Its job is to analyze raw corpus content
and produce extraction instructions before approved assets are generated.
`app/ingestion/semantic_analyzer.py` classifies unlabeled enterprise corpus into
reviewable candidate intent classes and flags human-review needs. Runtime uses
`AnswerBuilder` to project validated flow/user-task/tool/event definitions.

Tasks and tools are normalized with this boundary:

```text
task
  -> reusable unit of work
  -> contains tools

frontend_tool
  -> UI/channel interaction such as submit, click, choose, upload, or confirm

backend_tool
  -> backend invocation through API, gRPC, MCP, event, database, manual, or
     another configured protocol
```

Tools are the lowest capability level and must be approved before runtime can
reference them. Causal assertions are governed assets in `causality_kb`, not
free graph edges.

Extraction instructions is recommendation-only. It does not write final JSON and does not load Neo4j. JSON validation, artifact writing, audit, and graph loading stay custom and deterministic.

## Future Replacement Strategy
Replace local loading with GraphRAG, ETL, or custom pipelines by implementing `KnowledgeIngestionProvider`.

## Pretrained Base Strategy
The platform does not train a custom model from scratch. The reusable language
base comes from:

- the existing LLM used for structured extraction
- the enterprise memory accumulated in `asset_catalog`

That means the generic language understanding is pre-trained, while the
enterprise-specific canonicalization evolves from approved assets, aliases, and
review history already stored in the platform.
