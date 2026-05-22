# Ingestion Pipeline

## Purpose
Provide a deterministic ingestion pipeline that turns raw banking corpus files into reviewed, validated, auditable graph-ready artifacts.

## Responsibilities
- Own the ingestion sequence from corpus scan to artifact writing.
- Keep parsing, schema validation, file writing, graph loading, and audit deterministic.
- Allow AutoGen agents to recommend findings without letting agents write final JSON directly.
- Produce an audit record for every extraction run.
- Keep LangGraph optional and use it when branching, retries, or human-review workflow state are needed.

## Component Ownership
| Step | Owner | Current component | Notes |
|---|---|---|---|
| Scan corpus | Custom deterministic | `CorpusFlowLoader.load_corpus` | Finds supported files in stable sorted order. |
| Parse documents | Custom deterministic | `CorpusFlowLoader` | Reads text, CSV/MD/YAML/JSON/BPMN as text, PDFs with `pdftotext`/`pdftoppm`, images as vision inputs, DOCX via stdlib zip/XML extraction. |
| Reason over concepts | AutoGen recommendation | `AutoGenIngestionReasoningProvider` | Optional. Produces findings only; does not write JSON. |
| Resolve ambiguity | AutoGen recommendation plus later human review | `AutoGenIngestionReasoningProvider` | Useful for phrases such as "bajar cuota" where multiple flows may be plausible. |
| Extract normalized JSON | LLM extractor constrained by schema | `CorpusFlowLoader.extract_documents` | Uses `_schema_prompt` and optional agent findings. |
| Validate JSON | Custom deterministic | `normalize_and_validate` and `_normalize_*` | Rejects bad schema, missing references, and backend operations modeled as user tasks. |
| Write artifacts | Custom deterministic | `CorpusFlowLoader.write_result` | Writes preview or applied flow/user-task/action-registry JSON. |
| Audit ingestion | Custom deterministic | `IngestionPipelineService` | Writes `data/processed/ingestion_audit/ingestion_run_*.json`. |
| Load Neo4j | Custom deterministic | `tools/push_flows_to_neo4j.py` | Uses Cypher MERGE and constraints. |
| Orchestrate branches/retries | Optional LangGraph | `LangGraphIngestionPipelineService` | Use when retries, human-review state, or conditional branches justify it. |

## Data Flow
`raw corpus -> custom scan/parse -> optional AutoGen findings -> LLM schema extraction -> custom validation -> preview/apply JSON -> audit record -> Neo4j graph load`

## Main Components
- `app.ingestion.pipeline.IngestionPipelineService`
- `app.ingestion.pipeline.LangGraphIngestionPipelineService`
- `app.ingestion.pipeline.IngestionPipelineConfig`
- `app.ingestion.llm_flow_loader.CorpusFlowLoader`
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
