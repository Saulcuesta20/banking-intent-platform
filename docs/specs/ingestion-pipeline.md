# Ingestion Pipeline

## Purpose
Provide a deterministic ingestion pipeline that turns raw banking corpus files into reviewed, validated, auditable graph-ready artifacts.

## Responsibilities
- Own the ingestion sequence from corpus scan to artifact writing.
- Keep parsing, schema validation, file writing, graph loading, and audit deterministic.
- Classify mixed enterprise corpus without requiring pre-labeled intent files.
- Allow AutoGen agents to recommend findings without letting agents write final JSON directly.
- Produce human-review artifacts when semantic classification is ambiguous or risky.
- Produce an audit record for every extraction run.
- Keep LangGraph optional and use it when branching, retries, or human-review workflow state are needed.

## Component Ownership
| Step | Owner | Current component | Notes |
|---|---|---|---|
| Scan corpus | Custom deterministic | `CorpusFlowLoader.load_corpus` | Finds supported files in stable sorted order. |
| Parse documents | Custom deterministic | `CorpusFlowLoader` | Reads text, CSV/MD/YAML/JSON/BPMN as text, PDFs with `pdftotext`/`pdftoppm`, images as vision inputs, DOCX via stdlib zip/XML extraction. |
| Semantic analysis | LLM or heuristic recommendation | `SemanticAnalyzerService` | Classifies mixed corpus fragments into candidate intent classes, knowledge types, processes, systems, and review needs. |
| Reason over concepts | AutoGen recommendation | `AutoGenIngestionReasoningProvider` | Optional. Produces findings only; does not write JSON. |
| Resolve ambiguity | AutoGen recommendation plus later human review | `AutoGenIngestionReasoningProvider` | Useful for phrases such as "bajar cuota" where multiple flows may be plausible. |
| Extract normalized JSON | LLM extractor constrained by schema | `CorpusFlowLoader.extract_documents` | Uses `_schema_prompt` and optional agent findings. |
| Validate JSON | Custom deterministic | `normalize_and_validate` and `_normalize_*` | Rejects bad schema, missing references, backend operations modeled as user tasks, and adds deterministic concept aliases. |
| Write artifacts | Custom deterministic | `CorpusFlowLoader.write_result` | Writes preview or applied flow/user-task/action-registry JSON. |
| Audit ingestion | Custom deterministic | `IngestionPipelineService` | Writes `data/processed/ingestion_audit/ingestion_run_*.json`. |
| Human review | Custom deterministic | `IngestionPipelineService` | Writes `data/processed/human_review/ingestion_review_*.json` when review is required. |
| Load Neo4j | Custom deterministic | `tools/push_flows_to_neo4j.py` | Uses Cypher MERGE and constraints. |
| Orchestrate branches/retries | Optional LangGraph | `LangGraphIngestionPipelineService` | Use when retries, human-review state, or conditional branches justify it. |

## Data Flow
`raw enterprise corpus -> custom scan/parse -> semantic analyzer -> optional AutoGen findings -> LLM schema extraction -> custom validation + concept alias normalization -> preview/apply JSON -> audit + human review -> Neo4j graph load`

## Main Components
- `app.ingestion.pipeline.IngestionPipelineService`
- `app.ingestion.pipeline.LangGraphIngestionPipelineService`
- `app.ingestion.pipeline.IngestionPipelineConfig`
- `app.ingestion.llm_flow_loader.CorpusFlowLoader`
- `app.ingestion.semantic_analyzer.SemanticAnalyzerService`
- `app.knowledge_graph.vocabulary.ConceptVocabulary`
- `app.ingestion.reasoning.AutoGenIngestionReasoningProvider`
- `tools/extract_flows_from_corpus.py`
- `tools/push_flows_to_neo4j.py`

## Commands
Preview extraction without agents:

```bash
make extract
```

Preview extraction with deterministic role guidance:

```bash
make extract-reasoning
```

Preview extraction with real AutoGen agents:

```bash
make extract-autogen
```

Preview extraction with LangGraph orchestration:

```bash
make extract-langgraph
make extract-autogen-langgraph
```

Apply extraction to `data/flows`, `data/user_tasks`, and `data/action_registry`:

```bash
make extract-apply
make extract-autogen-apply
```

Load applied artifacts into Neo4j:

```bash
make graph-load
```

## LangGraph Decision
LangGraph is integrated as an optional orchestration path. Use it when the workflow needs durable state or branches such as:

- validation failed -> retry extraction with validation errors
- ambiguity detected -> route to human review
- human rejected -> send back to extraction with comments
- graph verification failed -> rollback or halt deployment

For simple linear extraction, the custom pipeline is still simpler and more auditable.

## Human Review Loop
Enterprise corpus is not expected to arrive pre-labeled as Q&A, guided use case,
or process execution. The semantic analyzer produces candidate classifications,
not final truth. If a document mixes signals or touches approval/risk, the
pipeline writes a pending review file:

```text
data/processed/human_review/ingestion_review_*.json
```

A reviewer can approve, reject, or document corrections before graph loading.
This lets the same ingestion process move between companies: each enterprise can
bring its own manuals, policies, wikis, BPMN, APIs, and legacy-system catalogs,
then tune the extracted artifacts through human intervention.
