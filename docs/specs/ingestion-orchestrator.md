# Ingestion Pipeline

## Purpose
Provide a deterministic ingestion orchestrator that turns raw banking corpus files into reviewed, validated, auditable graph-ready artifacts.

## Responsibilities
- Own the ingestion sequence from corpus scan to artifact writing.
- Keep parsing, schema validation, file writing, graph loading, and audit deterministic.
- Classify mixed enterprise corpus without requiring pre-labeled intent files.
- Allow role-based extraction instructions to recommend findings without letting extraction instructions write final JSON directly.
- Produce human-review artifacts when semantic classification is ambiguous or risky.
- Produce an audit record for every extraction run.
- Keep LangGraph optional and use it when branching, retries, or human-review workflow state are needed.

## Component Ownership
| Step | Owner | Current component | Notes |
|---|---|---|---|
| Scan corpus | Custom deterministic | `CorpusFlowLoader.load_corpus` | Finds supported files in stable sorted order. |
| Parse documents | Custom deterministic | `CorpusFlowLoader` | Reads text, CSV/MD/YAML/JSON/BPMN as text, PDFs with `pdftotext`/`pdftoppm`, images as vision inputs, DOCX via stdlib zip/XML extrtool. |
| Semantic analysis | LLM or heuristic recommendation | `SemanticAnalyzerService` | Classifies mixed corpus fragments into candidate intent classes, knowledge types, processes, systems, and review needs. |
| Reason over entities | Role-based recommendation | `RoleBasedExtractionInstructionBuilder` | Optional. Produces findings only; does not write JSON. |
| Resolve ambiguity | Role-based recommendation plus later human review | `RoleBasedExtractionInstructionBuilder` | Useful for phrases such as "bajar cuota" where multiple flows may be plausible. |
| Extract normalized JSON | LLM extractor constrained by schema | `CorpusFlowLoader.extract_documents` | Uses `_schema_prompt` and optional agent findings. |
| Validate JSON | Custom deterministic | `normalize_and_validate` and `_normalize_*` | Rejects bad schema, missing references, backend operations modeled as user tasks, and adds deterministic entity synonym aliases currently stored as concept aliases. |
| Write artifacts | Custom deterministic | `CorpusFlowLoader.write_result` | Writes preview or applied flow/user-task/tool-registry JSON. |
| Audit ingestion | Custom deterministic | `IngestionOrchestratorService` | Writes `data/processed/ingestion_audit/ingestion_run_*.json`. |
| Human review | Custom deterministic | `IngestionOrchestratorService` | Writes `data/processed/human_review/ingestion_review_*.json` when review is required. |
| Load Neo4j | Custom deterministic | `tools/extract_flows_from_corpus.py --apply` | Uses Cypher MERGE and constraints. |
| Orchestrate branches/retries | Optional LangGraph | `LangGraphIngestionOrchestratorService` | Use when retries, human-review state, or conditional branches justify it. |

## Data Flow
`raw enterprise corpus -> custom scan/parse -> semantic analyzer -> optional role-based findings -> LLM schema extraction -> custom validation + entity synonym normalization -> preview/apply JSON -> audit + human review -> Neo4j graph load`

## Main Components
- `app.ingestion.orchestrator.IngestionOrchestratorService`
- `app.ingestion.orchestrator.LangGraphIngestionOrchestratorService`
- `app.ingestion.orchestrator.IngestionOrchestratorConfig`
- `app.ingestion.llm_flow_loader.CorpusFlowLoader`
- `app.ingestion.semantic_analyzer.SemanticAnalyzerService`
- `app.knowledge_base.vocabulary.ConceptVocabulary` currently acts as entity vocabulary compatibility code.
- `app.ingestion.orchestrator.RoleBasedExtractionInstructionBuilder`
- `tools/extract_flows_from_corpus.py`
- `tools/extract_flows_from_corpus.py --apply`

## Commands
Preview extraction without agents:

```bash
python tools/extract_flows_from_corpus.py --raw-dir data/raw
```

Preview extraction with deterministic role-based extraction instructions:

```bash
python tools/extract_flows_from_corpus.py \
  --raw-dir data/raw \
  --build-extraction-instructions
```

Preview extraction with LangGraph orchestration:

```bash
python tools/extract_flows_from_corpus.py \
  --raw-dir data/raw \
  --build-extraction-instructions \
  --max-validation-retries 1 \
  --require-human-review
```

Apply extraction to `Neo4j`, `Neo4j UserTask nodes`, and `graph Tool nodes`:

```bash
ingest --raw data/raw/enterprise_dump_2026 --apply
```

Load applied artifacts into Neo4j:

```bash
kb reset-ingest --raw data/raw/enterprise_dump_2026
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
