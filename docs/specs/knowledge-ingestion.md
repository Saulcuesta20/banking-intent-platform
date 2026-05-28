# Knowledge Ingestion

## Purpose
Load external banking knowledge from raw documents into normalized flow and user task representations.

## Responsibilities
- Accept PDF, Markdown, HTML, wiki pages, JSON, OpenAPI/Swagger, BPMN, and raw domain notes.
- Extract concepts, actions, business events, flows, user tasks, and concept links.
- Detect candidate runtime intent classes from unlabeled enterprise text.
- Create flow plans and decompose them into reusable user tasks during ingestion.
- Build a single action registry from all discovered `front_actions` and `back_actions`.
- Persist processed metadata for graph loading.

## Main Components
- File source scanner
- Document parser registry
- Deterministic ingestion pipeline service
- Ingestion reasoning service
- Semantic analyzer and classifier
- AutoGen ingestion reasoning provider
- LLM-assisted corpus extractor
- `FlowKnowledgeLoader`
- `FileKnowledgeIngestionProvider`
- User task catalog loader
- Action registry builder
- Processed artifact writer

## Data Flow
Raw files are scanned and parsed by deterministic code, classified by semantic
analysis, optionally analyzed by ingestion reasoning agents, normalized into
flows and reusable user tasks, validated by deterministic schema rules, written
as preview or applied artifacts, registered as front/back actions, and recorded
in processed metadata plus ingestion audit and optional human-review records.

## Example Input/Output
Input: `data/flows/loan_refinance.flow.json`

Output: flows, reusable user tasks, resolved front/back actions, concepts, and a derived action registry.

## Interfaces
- `app/ingestion/providers.py::KnowledgeIngestionProvider.ingest(path)`
- `app/ingestion/pipeline.py::IngestionPipelineService.run(config)`
- `DocumentParser.parse(path)`
- processed artifact writer in `app/ingestion/flow_loader.py`

## Implementation Notes
MVP ingestion loads flow JSON and user task JSON records through `app/ingestion/flow_loader.py`, records file metadata and an action registry in processed output, and delegates approved graph persistence to `app.knowledge_graph.service.KnowledgeGraphService`. LLM-assisted corpus extraction lives in `app/ingestion/llm_flow_loader.py` and can write `data/action_registry/actions.registry.json`. The extraction command is coordinated by `app/ingestion/pipeline.py`, which owns sequencing and audit.

Agentic reasoning belongs in ingestion, not runtime planning. `app/ingestion/reasoning.py` defines a provider interface backed by `AutoGenIngestionReasoningProvider`. Its job is to analyze raw corpus content and produce extraction guidance before flow JSON is generated. `app/ingestion/semantic_analyzer.py` classifies unlabeled enterprise corpus into reviewable candidate intent classes and flags human-review needs. Runtime uses `AnswerBuilder` to project validated flow/user-task definitions.

AutoGen is recommendation-only. It does not write final JSON and does not load Neo4j. JSON validation, artifact writing, audit, and graph loading stay custom and deterministic.

## Future Replacement Strategy
Replace local loading with GraphRAG, ETL, or custom pipelines by implementing `KnowledgeIngestionProvider`.
