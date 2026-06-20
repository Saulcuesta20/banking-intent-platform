# Federated Ingestion Architecture

## Purpose
Define the LLM-first, LangGraph-coordinated ingestion topology that normalizes
assets and relations before projecting them into federated logical knowledge
bases.

## Main Ideas
- LangGraph remains the orchestration backbone.
- LLM extracts candidate assets and candidate causality/process/rule/plan/QA
  structures from raw corpus.
- Local services normalize canonical asset names, aliases, and relation types.
- Ingestion also builds transaction-scoped groupings:
  - `ruleset` for business rules that share one business transaction
  - `asset_set` for the full bundle of assets related to one business transaction
- `asset_catalog` remains the single unified inventory.
- Logical KBs (`business_model_kb`, `rules_kb`, `process_kb`, `planning_kb`,
  `qa_kb`, `document_kb`, `causality_kb`) own assets semantically.
- Vector memory is federated by collection in Qdrant, but the current
  contract only writes approved `qa` and source `document` assets there.
- In the federated topology, `entity` is the canonical business-model asset
  family. Legacy `concept` and `ontology` names are normalized to `entity`
  instead of being treated as separate business-model families.

## New Components
- `app/ingestion/relation_normalization.py`
  - canonical relation registry loader
  - relation alias normalization
  - optional vector-assisted relation resolution
- `app/ingestion/federated_topology.py`
  - logical KB topology
  - vector/document routing plan
  - alias memory and relation memory payload builders
- `config/ingestion/relation_registry.yaml`
  - canonical relation families and aliases
- `config/ingestion/federated_topology.yaml`
  - logical KB routing and vector collection layout

## Federated Vector Collections
- `knowledge_assets`
- `kb_qa_assets`
- `kb_document_assets`

Alias and relation helper indexes remain separate:

- `asset_alias_memory`
- `relation_alias_memory`

## Execution Flow
```text
LangGraph ingestion
  -> corpus loading
  -> flow/task/tool extraction
  -> LLM asset extraction
  -> relation hint detection
  -> relation normalization
  -> canonical asset alignment
  -> asset_catalog persistence
  -> federated document routing
  -> federated vector routing
  -> graph projection
```

## Current Tradeoff
The federated architecture is implemented end to end, but semantic quality still
depends on prompt/schema coverage and alignment quality. The next improvement
loop should focus on:
- stronger chunk-level LLM extraction
- better asset alignment using vector similarity against approved catalog assets
- stronger causality resolution for source/target canonicalization
