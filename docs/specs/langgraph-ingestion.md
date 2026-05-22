# LangGraph Ingestion Orchestration

## Purpose
Use LangGraph as an optional orchestration layer for ingestion runs that need branches, retries, or explicit human-review metadata.

## Where It Is Integrated
LangGraph is integrated in:

- `app/ingestion/pipeline.py::LangGraphIngestionPipelineService`
- `tools/extract_flows_from_corpus.py --langgraph`
- `Makefile` targets `extract-langgraph` and `extract-autogen-langgraph`

It does not replace the deterministic ingestion components. It coordinates them.

## What LangGraph Controls
| Concern | LangGraph responsibility |
|---|---|
| Node sequence | Runs scan/parse, extract/validate, write artifacts, write audit. |
| Conditional routing | Routes extraction failures to retry or failure halt. |
| Retry boundary | Uses `max_validation_retries` to decide whether to retry extraction/validation. |
| Human review marker | Preserves `require_human_review` in artifact/audit metadata. |
| Final state | Returns the same `IngestionPipelineResult` contract as the custom pipeline. |

## What LangGraph Does Not Control
| Concern | Owner |
|---|---|
| Corpus parsing | Custom `CorpusFlowLoader`. |
| AutoGen reasoning | `AutoGenIngestionReasoningProvider`, optional. |
| JSON schema | `CorpusFlowLoader._schema_prompt`. |
| JSON validation | `CorpusFlowLoader.normalize_and_validate` and `_normalize_*`. |
| File writing | `CorpusFlowLoader.write_result`. |
| Neo4j loading | `tools/push_flows_to_neo4j.py`. |
| Runtime question answering | `IntentResolutionService` and retrieval/intent providers. |

## Graph Shape
```text
START
  -> scan_and_parse
  -> extract_and_validate
       -> retry extract_and_validate when validation/extraction fails and retries remain
       -> fail when validation/extraction fails and retries are exhausted
       -> write_artifacts when extraction is valid
  -> write_audit
  -> END
```

## Commands
Run extraction with LangGraph orchestration and deterministic LLM extraction:

```bash
make extract-langgraph
```

Run extraction with AutoGen recommendations plus LangGraph orchestration:

```bash
make extract-autogen-langgraph
```

Equivalent direct command:

```bash
OPENAI_API_KEY=... python tools/extract_flows_from_corpus.py \
  --raw-dir data/raw \
  --autogen-ingestion-reasoning \
  --langgraph \
  --max-validation-retries 1 \
  --require-human-review
```

## Implementation Notes
The implementation follows the LangGraph `StateGraph` model: each node is a Python function that reads and updates shared state, the graph starts with `START`, conditional edges route after extraction/validation, and `.compile().invoke(...)` executes the graph.

LangGraph is optional because simple linear extraction is still easier to audit with `IngestionPipelineService`. Use `LangGraphIngestionPipelineService` when the run needs retry/halt semantics, human-review metadata, or future expansion into more branches.

## Sources
- LangGraph Graph API: https://docs.langchain.com/oss/python/langgraph/graph-api
- LangGraph StateGraph reference: https://reference.langchain.com/python/langgraph/graph/state/StateGraph
- LangGraph conditional edges reference: https://reference.langchain.com/python/langgraph/graph/state/StateGraph/add_conditional_edges
