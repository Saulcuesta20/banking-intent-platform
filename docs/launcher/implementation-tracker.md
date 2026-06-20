# Launcher Implementation Tracker

## Purpose

This tracker is the working source of truth for the launcher architecture,
active code paths, verification status, and pending work.

## Current Status

- `[DONE]` Launcher shell is React + TypeScript + shadcn/ui.
- `[DONE]` Structured flow editing uses JSON Forms.
- `[DONE]` Frontend flow validation uses Zod.
- `[DONE]` Backend validation uses FastAPI + `AssetContractRegistry`.
- `[DONE]` Unified Catalog is the runtime source of truth for launcher assets.
- `[DONE]` Catalog explorer renders `Catalog` as the single top-level governed
  source instead of rendering backend projections as separate catalogs.
- `[DONE]` Lowdefy runtime, proxying, generated YAML pages, and launcher
  Lowdefy dependencies were removed from the active launcher path.
- `[DONE]` Launcher now runs on port `3000` only.
- `[TODO]` Ontology/business-model editor needs a contract-driven rebuild:
  current KB action can open an arbitrary owned asset instead of a dedicated
  business-model graph editor, and the canvas mixes governance/catalog
  relations with true business ontology relations.

## Current Architecture

```text
AssetSet YAML authoring
  -> load / ingest
  -> Unified Catalog
  -> review / validation / deployment
  -> backend projections (graph, vector, document, relational)
  -> React launcher reads FastAPI
```

### Frontend Ownership

- React/shadcn owns navigation, layout, workspace, assets explorer, and right
  governance/detail panel.
- JSON Forms owns the structured flow editor form surface.
- Zod owns client-side validation for flow/task/action/tool editing.

### Backend Ownership

- FastAPI owns asset retrieval, validation, preview, version creation,
  lifecycle transitions, deployment, rollback, Ask integration, and execution.
- Unified Catalog owns canonical asset versions and active runtime visibility.
- Graph, vector, document, and relational stores are backend projections only.

## Key Runtime Locations

| Area | Path / URL |
|---|---|
| Session rules | `AGENTS.md` |
| Launcher app | `app/launcher/src` |
| Flow editor package | `app/launcher/plugins/asset-editors/src/editors/flow-editor` |
| Module manifests | `app/launcher/modules` |
| Generated module registry | `app/launcher/public/module-registry.json` |
| Launcher README | `app/launcher/README.md` |
| Launcher runtime doc | `app/launcher/docs/module-runtime.md` |
| Architecture doc | `docs/launcher/architecture.md` |
| Tech stack doc | `docs/launcher/tech-stack.md` |
| AssetSet source folders | `app/assets/catalog/modules/<module>/assetsets/<set>/` |
| Launcher URL | `http://localhost:3000` |
| FastAPI URL | `http://127.0.0.1:8030` |

## Commands

### Launcher

```bash
npm --prefix app/launcher run generate:module-registry
npm --prefix app/launcher run dev
npm --prefix app/launcher run build
```

### Catalog Reload

```bash
./.venv/bin/python -m app.platform_cli reset-ingest --catalog-only --replay-staged --no-start-databases
```

### Asset Queries

```bash
./.venv/bin/python -m app.platform_cli query --asset-type flow --tree --format tree
./.venv/bin/python -m app.platform_cli query --metadata --tree
```

## Ontology Editor Rebuild Strategy

### 2026-06-19 Business/Technical Entity Mapping

- `[DONE]` Updated the ontology/asset contracts to make
  `represented_by` / `represents` the canonical relation between a business
  entity and its technical representation.
- `[DONE]` Kept `materializes` / `materialized_in` as legacy compatibility
  aliases only. Ingest and editor normalization now convert them to
  `represents` / `represented_by`.
- `[DONE]` Clarified the field contract:
  - `subtype` is the business/structural stereotype inside a layer, for
    example `party/customer`, `organization/department`, or
    `business_resource/table`.
  - `technical_type` is the implementation form, for example `table`, `api`,
    `dataset`, or `service`; it is not a synonym for `subtype`.
- `[DONE]` Ingestion now preserves LLM-provided entity `subtype`,
  `technical_type`, `attributes`, and entity relations. Technical resources
  such as tables stay as `asset_type: entity` with
  `structural_layer: business_resource`.
- `[DONE]` The ontology endpoint now returns `asset_type`, `subtype`,
  `technical_type`, and `relation_family` for canvas filtering and display.
- `[DONE]` The launcher KB action now opens a dedicated virtual
  `ontology_graph` editor context instead of selecting the first asset owned by
  the KB. The virtual context is read as an aggregate KB canvas, not versioned
  as a governed asset.
- `[DONE]` The ontology editor schema/UI schema now exposes `structural_layer`,
  `subtype`, `technical_type`, `semantic_space`, and the canonical relation
  list including `represented_by` / `represents`.
- `[DONE]` The ontology canvas sidebar now includes filters for business vs
  technical representation and relation family. Node labels and the right
  detail panel show layer, subtype/stereotype, and technical type.

Affected paths:

- `config/asset_registry/asset_types.yaml`
- `config/model/extraction_schema.yaml`
- `config/ontology/universal_layers.yaml`
- `config/ingestion/relation_registry.yaml`
- `config/ingestion/relation_type_patterns.yaml`
- `docs/specs/ontology-search-spaces.md`
- `app/ingestion/asset_pipeline.py`
- `app/api.py`
- `app/launcher/src/App.tsx`
- `app/launcher/src/components/AssetInlineEditor.tsx`
- `app/launcher/src/components/AssetDetailPanel.tsx`
- `app/launcher/src/types.ts`
- `app/launcher/plugins/asset-editors/src/editors/ontology-editor/`
- `tests/test_asset_pipeline.py`

Verification:

- `[DONE]` `.venv/bin/pytest -q tests/test_asset_pipeline.py tests/test_asset_registry.py`
  (14 passed, 1 existing Qdrant insecure-connection warning)
- `[DONE]` `node --test app/launcher/plugins/asset-editors/src/editors/ontology-editor/validators.test.js`
- `[DONE]` `.venv/bin/python -m py_compile app/ingestion/asset_pipeline.py app/api.py`
- `[DONE]` `npm --prefix app/launcher run lint`
- `[DONE]` `npm --prefix app/launcher run build`
  (passed; Vite chunk-size warning only)

Remaining TODO:

- `[TODO]` Add full ontology graph editing/persistence for creating/updating
  business-to-technical relations from the canvas. Current aggregate KB canvas
  can filter and display the relationship model; governed save still belongs to
  the underlying entity asset/version.
- `[TODO]` Move relation-family classification from the temporary API helper
  into the shared relation registry so API, ingest, graph projection, and
  editor use one source of truth.

### 2026-06-19 Diagnosis

- Technology check: the ontology editor is already in the required plugin path
  (`app/launcher/plugins/asset-editors/src/editors/ontology-editor/`) and uses
  React, JSON Forms, Zod, tldraw, and inline shared styles.
- The contextual KB action exists in `AssetExplorer` as `Canvas de ontología`,
  but `openKnowledgeBaseEditor()` currently selects the first catalog asset
  owned by that KB and opens `AssetInlineEditor`. Because `AssetInlineEditor`
  only activates `OntologyEditorView` for `asset_type === "entity"`, the KB
  canvas can open the wrong document/editor instead of a dedicated KB graph.
- `GET /catalog/knowledge-bases/business_model_kb/ontology?environment=dev`
  returned 60 entities and 203 relations with the backend running locally.
  The payload includes many governance/container relations such as
  `asset_set -> entity` / `groups_entity`; these should not be the default
  business-model graph because they hide the entity-to-entity ontology.
- The current canvas/sidebar filters cover a small subset only:
  `assetType`, `structural_layer`, text search, and quick relation presets.
  It does not yet expose contract-level facets for `semantic_space`,
  relationship family/type, direction, endpoint asset type, evidence/source,
  projection state, or business-vs-governance graph mode.
- Current ontology helper constants still contain legacy visual roles and
  generic relation names (`supports`, `depends_on`, `enables`, etc.). They
  need to align with the updated ontology/asset contracts: `semantic_space`,
  `structural_layer`, `business_resource`, `entity`, and catalog-owned
  aliases/synonyms.

### Target Design

- Add a dedicated knowledge-base ontology editor mode so opening a KB creates a
  virtual graph document (`asset_type: "ontology_graph"` or equivalent local
  editor context) instead of choosing an arbitrary owned asset.
- Make the default view `Business Model`: entity-to-entity relationships only,
  grouped by `semantic_space` and `structural_layer`; external assets
  (`flow`, `user_task`, `tool`, `business_rule`, `asset_set`, documents) appear
  only in an explicit `Impact/Governance` view or when expanded.
- Redesign the right sidebar as a combined filter/inspector surface:
  filter chips/tags for semantic spaces, structural layers, asset types,
  business resources, relationship families, direction, and endpoint type; the
  selected entity/relation detail stays below those filters.
- Keep the canvas as the main tldraw surface, but add contract-aware views:
  `Business Model`, `Impact`, `Semantic Spaces`, `Layer Map`, and
  `Relationship Matrix`.
- Add ontology actions expected by the modeler: create entity, create business
  relationship, create semantic space, assign structural layer, edit aliases
  and attributes, expand/collapse neighborhood, show incoming/outgoing/both,
  validate model, export JSON, reload, fit/zoom, and open selected item in the
  structured form.
- Extend the ontology endpoint/normalizer to classify relations by family:
  `business_fact`, `classification`, `search_context`, `governance`,
  `evidence`, and to expose `facets` so the UI filters are contract-driven
  rather than inferred from whichever nodes are visible.

### Proposed Task Plan

1. Fix KB canvas entry: introduce a dedicated ontology graph editor context for
   knowledge-base nodes and keep asset editing separate from KB graph editing.
2. Normalize ontology graph payloads: split business entities/relations from
   governance or catalog relations, preserve legacy aliases (`concept`,
   `business_layer`) only as compatibility inputs.
3. Rebuild the sidebar filters/inspector around ontology contract facets:
   `semantic_space`, `structural_layer`, `asset_type`, relation family/type,
   direction, source/target type, evidence, and status.
4. Rebuild canvas views: default `Business Model` plus optional
   `Impact/Governance`, `Semantic Spaces`, `Layer Map`, and relationship
   matrix modes.
5. Add complete graph actions and validation states inside the plugin without
   creating inline editors in `AssetInlineEditor.tsx`.
6. Add/update tests: helper normalizer tests, ontology validator tests,
   Playwright stubbed E2E for the KB canvas, and a real smoke test when
   FastAPI + launcher are running.

### Verification Snapshot

- `node --test app/launcher/plugins/asset-editors/src/editors/ontology-editor/validators.test.js`
  passed.
- `npm --prefix app/launcher run build` passed; Vite reported only the existing
  chunk-size warning.
- Playwright against the live launcher confirmed the `Canvas de ontología`
  action exists and can be clicked, but it did not show the canvas; the UI
  remained in an asset editor (`Edit CBU`), matching the KB-entry bug above.
- `npm --prefix app/launcher run test:e2e -- --grep "business model"` was not
  conclusive in this sandbox because Vite preview failed to bind
  `127.0.0.1:4173` with `EPERM`.

## What Changed In This Migration

### Completed

- Added a tldraw-powered business model canvas to the ontology-editor plugin: updated JSON Schema/UI schema, new Zod validators + layout metadata, inline graph toolbar (filters, auto-layout, fit view), dual creation forms, and persisted node coordinates; registered the new `tldraw` dependency and refreshed editor unit tests.
- Rebuilt the ontology-editor structured surface to match `docs/launcher/designs/ontology-canvas-prototype.html`, preserving the filters + tldraw canvas but moving the entity detail into the global right-side panel, adding a Canvas/Form toggle, entity/relation creation helpers, toolbar actions (Formulario, Ajustar vista, Exportar, Recargar), fit view controls, and contextual hints that jump editors into form mode.
- Added a contextual “Editar ontología” action to each knowledge base node in the asset explorer and wired selection state/handlers from the editor through AssetInlineEditor → App so the right-hand governance panel always shows the active ontology node; the E2E spec now asserts the reduced two-panel canvas and the ontology detail entry point.
- Added Playwright-based E2E coverage (with stubbed catalog APIs and an exported screenshot) for the business model editor under `app/launcher/tests/e2e/`.
- Catalog metadata + tree now expose real knowledge bases, and a new `/catalog/knowledge-bases/{kb}/ontology` endpoint powers the aggregated business-model graph view inside the launcher.
- Removed launcher `lowdefy` npm dependency and lockfile references.
- Removed `dev:editor-runtime`, `/lowdefy` proxying, and page generation
  scripts from the active launcher.
- Replaced `generate:editor-runtime` with `generate:module-registry`.
- Removed generated YAML editor pages under `app/launcher/pages/`.
- Removed Lowdefy block wrapper files under
  `app/launcher/plugins/asset-editors/src/blocks/` and related package glue.
- Renamed module process manifest field `lowdefyPage` to `editorRoute`.
- Removed `lowdefy_page` and `lowdefy_url` from launcher runtime payloads.
- Updated form asset manifests from `renderer: lowdefy` to `renderer: react`
  and replaced `lowdefy` tags with `jsonforms`.
- Updated docs to describe the active React/JSON Forms architecture.
- Documented canonical editor architecture in AGENTS.md and agent config.
- Added editor plugin pattern as mandatory guideline for all new editors.
- Created ontology-editor, business-rule-editor, navigation-editor plugins
  with schema, ui-schema, helpers, components, index, validators.test, MOCKUP.
- Fixed flow-editor/components.js SWC parser error by extracting deep nested
  h() calls into named sub-components (FlowTaskIdentitySection,
  FlowTaskLifecycleSection, FlowTaskActionsSection, FlowTaskActionCard,
  FlowTaskToolsSection, FlowTaskToolCard).
- Created MOCKUP.md for flow-editor plugin.
- Created menu-editor plugin with schema, ui-schema, helpers, components,
  index, validators.test (6/6 pass), MOCKUP.
- Created domain-editor plugin with schema, ui-schema, helpers, components,
  index, validators.test (6/6 pass), MOCKUP.
- Registered menu + domain editors in AssetInlineEditor.tsx.
- Removed legacy `formSchema.ts` (not imported anywhere).
- Removed legacy `FormField`, `ModuleFormField`, `ModuleFormDefinition`
  types from `types.ts` (not imported anywhere).
- Converted all 5 UI schemas to GridLayout (flow-editor.ui-schema.json,
  user-task.ui-schema.json, ontology, business-rule, navigation).
- Fixed all 6 lint errors in AssetInlineEditor.tsx: replaced @ts-ignore
  with @ts-expect-error, removed setState-in-effect, replaced dynamic
  component creation with inline conditional rendering.
- Changed default `project_knowledge_bases` to `False` in
  `app/ingestion/orchestrator.py` to prevent graph KB writes during ingest.
- Added `project_knowledge_bases=False` to `cli ingest` command.
- Added negative flow rules to `config/model/extraction_schema.yaml`:
  flows must be multi-step processes; rejects inquiries, Quiero, setup,
  exception handling, single-step operations.
- Strengthened LLM system prompt in `llm_flow_loader.py` with precise
  flow definition and rejection criteria.
- Added post-LLM flow filtering in `_normalize_flow()` that rejects
  flows with names containing inquiry, status check, Quiero, setup,
  etc. Added single_task_flow_candidate warning for flows with < 2 tasks.
- Changed `EnterpriseAsset.status` default from `"approved"` to `"draft"`.
- Changed `AssetCandidate.status` default from `"approved"` to `"draft"`.
- Changed `FlowAssetAdapter` to use `"draft"` instead of `"approved"`.
- Changed `ExecutableDefinitionWriter` to use `"draft"` for new flows
  and processes instead of `"approved"`.
- Refactored `AssetInlineEditor.tsx` layout: removed 2-column grid,
  moved Actions to bottom of form, made Governance a compact horizontal
  bar, removed unused `mode` state.
- Made flow-editor grids responsive: all `1fr 1fr`, `1fr 140px 1fr 1fr`,
  `1fr 170px 1fr 1fr`, `1fr 1fr 1fr` converted to
  `repeat(auto-fit, minmax(Npx, 1fr))`.
- Added `uses_entity` to `flow.valid_relations` and
  `user_task.valid_relations` in asset registry.
- Added `find_referencers()` to `AssetCatalogStore` (SQLite inbound
  query using `idx_relationship_target` index) and
  `EnterpriseAssetRepository` (in-memory O(n) scan).
- Created `app/events.py` domain events module with `AssetStatusChanged`
  event, `EventBus` class, and `emit_asset_status_change()` helper.
- Hardened flow filter: now rejects single-task flows (MUST have >= 2
  user_task_refs), plus 30+ reject patterns (inquiry, quiero, setup,
  exception, notifications, reports, deploy, etc). Filter is hardcoded,
  not LLM-dependent.
- Removed hardcoded flow filters. LLM classifies assets from its training.
  System prompt provides precise definitions for each asset type
  (flow, user_task, tool, entity, business_rule, process, plan, qa,
  causality, container assets). No post-extraction keyword filtering.
- `AssetCandidate`, `EnterpriseAsset`, and `AssetCatalogStore` now carry
  `business_layer` so ontology classifications are queryable in SQLite,
  payloads, and downstream stores.
- `_entity_candidates` infers `business_layer` heuristically until the
  LLM provides explicit ontology output; canonicalization preserves the
  flag for persistence and projection.
- `config/model/extraction_schema.yaml` documents the universal ontology,
  adds `business_layer`/`entity_role` fields to entity payloads, and
  codifies Fase 0/Fase 4 guidance for LLM extraction.
- `config/ontology/universal_layers.yaml` defines the 8-layer ontology
  contract + role definitions consumed by ingestion and CLI reporting.
- `app/ingestion/orchestrator.py` now has explicit Fase 0 domain analysis
  (clarifying question) and Fase 4 validation/review nodes that run before
  catalog persistence, with quality scoring + review prompts.
- `app/platform_cli.py`/`kb stats` prints Knowledge Base summary plus a
  Universal Ontology Mapping table and Entity Roles summary sourced from
  `config/ontology/universal_layers.yaml`.
- Created `docs/launcher/ingest-lifecycle.md` with detailed 14-node
  LangGraph pipeline documentation.
- Neo4j projection now tags placeholder nodes (created only to anchor
  relations) with `placeholder=true` and omits `asset_type`, so they no
  longer inflate flow counts until the real asset is ingested.
- Added `config/ingestion/projection_rules.yaml` and updated `kb stats`
  to display `n/a` for asset types that intentionally skip graph
  projection, eliminating false-positive inconsistencies for documents,
  asset sets, QA, etc.
- Defaulted Zen runs to `deepseek-v4-flash` when no `INTENT_LLM_MODEL`
  is set so future ingest resets don't regress to `gpt-4o-mini`.
- Added `intent_llm_timeout_seconds` setting and wired it into the
  ingestion orchestrator + CLI tools so Opencode Zen calls can wait up to
  180s (env overrideable) without code edits.
- Hardened `CorpusFlowLoader` to split batches automatically when the LLM
  times out, returns 413s, or resets connections; single stubborn
  documents are now marked `_skipped` instead of aborting the run. Added
  pytest coverage for timeout retries and non-retryable errors.

### Affected Source Paths

- `app/launcher/package.json`
- `app/launcher/vite.config.ts`
- `app/launcher/scripts/module-utils.mjs`
- `app/launcher/scripts/generate-module-registry.mjs`
- `app/launcher/scripts/watch-modules.mjs`
- `app/launcher/runtime.py`
- `app/launcher/src/App.tsx`
- `app/launcher/src/api.ts`
- `app/launcher/src/types.ts`
- `app/launcher/src/formSchema.ts` (deleted)
- `app/launcher/eslint.config.js`
- `app/launcher/modules/**/*.json`
- `app/assets/catalog/modules/**/form-set/assets/*.yaml`
- `app/launcher/modules/**/form-set/assets/*.yaml`
- `app/launcher/plugins/asset-editors/src/editors/flow-editor/components.js`
- `app/launcher/plugins/asset-editors/src/editors/flow-editor/MOCKUP.md` (created)
- `app/launcher/plugins/asset-editors/src/editors/ontology-editor/` (created)
- `app/launcher/plugins/asset-editors/src/editors/business-rule-editor/` (created)
- `app/launcher/plugins/asset-editors/src/editors/navigation-editor/` (created)
- `app/launcher/plugins/asset-editors/src/editors/menu-editor/` (created)
- `app/launcher/plugins/asset-editors/src/editors/domain-editor/` (created)
- `app/launcher/plugins/asset-editors/src/editors/process-editor/` (created)
- `app/launcher/plugins/asset-editors/src/editors/tool-editor/` (created)
- `app/launcher/plugins/asset-editors/src/editors/qa-editor/` (created)
- `app/launcher/plugins/asset-editors/src/editors/plan-editor/` (created)
- `app/launcher/plugins/asset-editors/src/editors/user-task-editor/` (created)
- `app/launcher/plugins/asset-editors/src/editors/document-editor/` (created)
- `app/launcher/plugins/asset-editors/src/editors/configuration-editor/` (created)
- `app/launcher/plugins/asset-editors/src/editors/module-editor/` (created)
- `app/launcher/plugins/asset-editors/src/editors/form-editor/` (created)
- `app/launcher/tests/flow-editor.test.tsx` (created)
- `app/launcher/vitest.config.ts` (created)
- `app/ingestion/orchestrator.py` (IngestionGraphState, _persist_knowledge_node, EventBus wiring, Fase 0/4 nodes)
- `app/ingestion/asset_pipeline.py` (canonical entity extraction, business_layer inference)
- `app/ingestion/llm_flow_loader.py` (system prompt, batch size)
- `app/knowledge_base/search.py` (approved_only parameter)
- `app/events.py` (created)
- `tests/test_asset_registry.py` (draft-aware assertions)
- `tests/test_llm_flow_loader.py` (prompt assertion, batch test, KB stub)
- `tests/test_process_execution.py` (explicit status="approved")
- `app/events.py` (EventBus, AssetStatusChanged)
- `app/knowledge_base/catalog_store.py` (EventBus wiring, _projection_results, business_layer column/index)
- `app/knowledge_base/search.py` (VectorSearchAdapter, vector integration)
- `app/knowledge_base/models.py` (vector_results field, business_layer)
- `app/factory.py` (vector adapter wiring)
- `app/cli/__init__.py` (kb_query vector view)
- `app/platform_cli.py` (kb stats ontology summary)
- `config/model/extraction_schema.yaml` (ontology + entity fields)
- `config/ontology/universal_layers.yaml` (created)
- `app/config/settings.py` (ontology_layers_path wiring)
- `tools/kb_reset_load.py`, `tools/extract_flows_from_corpus.py` (pass ontology path to CanonicalAssetPipeline)
- `tests/test_asset_pipeline.py`, `tests/test_llm_flow_loader.py` (instantiate pipeline with ontology file)
- `config/asset_registry/asset_types.yaml` (semantic_space contract, entity relation contract, concept legacy alias)
- `config/ingestion/federated_topology.yaml` (semantic_space assigned to business_model_kb)
- `config/ingestion/projection_rules.yaml` (semantic_space projected to graph)
- `config/model/extraction_schema.yaml` (semantic_space extraction contract, structural_layer entity contract)
- `config/ontology/universal_layers.yaml` (construction_contract + relation_contract for spaces/layers/entities)
- `app/ingestion/asset_pipeline.py` (structural_layer canonical emission, concept/business_layer compatibility)
- `app/ingestion/llm_flow_loader.py` (semantic_space/structural_layer prompt + optional arrays)
- `app/ingestion/llm_flow_loader.py` (parallel LLM batch execution through `INGEST_LLM_PARALLEL_REQUESTS`)
- `app/ingestion/orchestrator.py` (semantic_space type registration, structural_layer validation)
- `app/knowledge_base/catalog_store.py` (structural_layer column/index/filter, business_layer fallback)
- `app/knowledge_base/adapters/graph/neo4j.py` (StructuralLayer projection + CLASSIFIES edges)
- `app/knowledge_base/search.py` (Ask asset search indexes structural_layer/semantic_space)
- `app/ask/service.py` (Ask trace payload includes structural_layers/semantic_spaces)
- `app/api.py` (ontology endpoint returns structural_layer and layer compatibility)
- `app/platform_cli.py` (`kb stats` counts Structural Layer Mapping)

## Verification

- `[DONE]` `node --test app/launcher/plugins/asset-editors/src/editors/ontology-editor/validators.test.js` (ontology canvas refresh)
- `[DONE]` `npm --prefix app/launcher run lint` (post-canvas rebuild)
- `[DONE]` `npm --prefix app/launcher run build`
- `[DONE]` `npm --prefix app/launcher run test:e2e` (Playwright)
- `[DONE]` `node --test app/launcher/plugins/asset-editors/src/editors/ontology-editor/validators.test.js`
- `[DONE]` `npm --prefix app/launcher run lint`
- `[DONE]` `npm --prefix app/launcher run build`
- `[DONE]` `npx playwright test --config app/launcher/playwright.config.ts`
- `[DONE]` `npx playwright test --config app/launcher/playwright.config.ts`
- `[DONE]` `./.venv/bin/pytest -q tests/test_cli_commands.py -k "catalog_asset_tree"`
- `[DONE]` `npm --prefix app/launcher run build` (tsc + vite, zero errors)
- `[DONE]` `npm --prefix app/launcher run lint` (zero errors)
- `[DONE]` `node --test` all editor unit tests (104/104 pass)
- `[DONE]` `vitest run` flow editor UI tests (5/5 pass)
- `[DONE]` Python verification: `project_knowledge_bases=True` (ingest writes to all stores)
- `[DONE]` Python verification: `EnterpriseAsset.status="draft"` by default
- `[DONE]` Python verification: `AssetCandidate.status="draft"` by default
- `[DONE]` Python verification: flow filter rejects "Quiero..." and "Inquiry" flows
- `[DONE]` Python verification: EventBus + AssetStatusChanged work correctly
- `[DONE]` `find_referencers()` added to catalog_store and repository
- `[DONE]` Dev server running on `http://localhost:3000` (HTTP 200)
- `[DONE]` `./.venv/bin/python -m app.platform_cli reset-ingest --catalog-only --replay-staged --no-start-databases`
- `[DONE]` `./.venv/bin/kb reset-ingest --raw data/raw` (catalog-only replay of richest staged run)
- `[DONE]` `./.venv/bin/kb stats` (Knowledge Base + ontology summary)
- `[DONE]` Cache-only ingestion run via custom `IngestionOrchestratorService` script (semantic_analysis=False) to replay the new corpus without live LLM calls; refreshed catalog + Neo4j + Qdrant projections (395 assets).
- `[FAIL]` Multiple attempts to run `kb reset-ingest` against Opencode Zen/Go endpoints (`https://opencode.ai/zen/v1`, `/zen/go`, direct `https://opencode.ai`) with models `gpt-5.1-codex` / `deepseek-v4-pro` all failed with Cloudflare 1010/401/404 (requests blocked before hitting model API).
- `[DONE]` Cache-only ingestion rerun after ontology refactor (`ingestion_run_20260616T014608Z`) – confirms business_layer coverage (unclassified=0 in `kb stats`).
- `[DONE]` EventBus wired in transition_asset_set and deploy_asset_set
- `[DONE]` _projection_results reads real deployment data
- `[DONE]` kb_query returns real vector search results
- `[DONE]` 9 editor plugins: 15/15 asset types have dedicated editors
- `[DONE]` GenericPayloadView removed from AssetInlineEditor.tsx
- `[DONE]` `data/raw/corporate_structure_and_offerings.md` added to document enterprise structure, offerings, and departments; ingestion cache updated with new flows (fl101, fl102), user tasks (ut401-403), and entities for Everyday Banking + ShieldGuard to keep extraction self-contained offline.
- `[DONE]` Cache-only ingestion run executed via `IngestionOrchestratorService` with semantic analysis disabled so we could replay the new corpus without external LLM calls; Neo4j/Qdrant projections refreshed from the resulting 395 canonical assets.
- `[DONE]` `./.venv/bin/python -m pytest tests/test_asset_registry.py tests/test_llm_flow_loader.py -v --tb=short`
- `[DONE]` `./.venv/bin/python -m pytest tests/test_asset_pipeline.py -v --tb=short`
- `[DONE]` `./.venv/bin/python -m pytest tests/test_asset_pipeline.py tests/test_llm_flow_loader.py -v --tb=short`
- `[DONE]` `./.venv/bin/pytest tests/test_cli_commands.py -k catalog_asset_tree -q`
- `[DONE]` `./.venv/bin/pytest tests/test_llm_flow_loader.py -q`
- `[DONE]` `./.venv/bin/pytest tests/test_settings.py -q`
- `[DONE]` `.venv/bin/python -m py_compile app/ingestion/asset_pipeline.py app/ingestion/llm_flow_loader.py app/ingestion/orchestrator.py app/knowledge_base/models.py app/knowledge_base/catalog_store.py app/knowledge_base/adapters/graph/neo4j.py app/knowledge_base/search.py app/ask/service.py app/api.py app/platform_cli.py`
- `[DONE]` `.venv/bin/pytest tests/test_asset_pipeline.py -q` (4/4)
- `[DONE]` `.venv/bin/pytest tests/test_llm_flow_loader.py -q` (27/27)
- `[DONE]` `.venv/bin/pytest tests/test_llm_flow_loader.py -q` (28/28, after parallel batch execution)
- `[DONE]` `.venv/bin/pytest tests/test_asset_registry.py tests/test_settings.py -q` (12/12)
- `[DONE]` `.venv/bin/pytest tests/test_agents.py tests/test_ask_langgraph_orchestration.py -q` (9/9)
- `[DONE]` `.venv/bin/pytest tests/test_knowledge_graph.py -q` (6/6)
- `[DONE]` Contract smoke check: asset registry has `semantic_space`, extraction schema has `semantic_space`, universal layers has `business_resource` and `construction_contract`.
- `[FAIL]` `.venv/bin/pytest tests/test_cli_commands.py -k catalog_asset_tree -q` failed on existing label expectation (`catalog` vs `Catalog`); not caused by ontology migration paths.
- `[DONE]` `.venv/bin/python -m py_compile app/ingestion/llm_flow_loader.py`
- `[DONE]` `.venv/bin/pytest tests/test_llm_flow_loader.py -q` (28/28, includes parallel batch execution)
- `[FAIL]` Full no-cache reset from raw with parallel LLM batches:
  `env INTENT_LLM_TIMEOUT_SECONDS=180 INGEST_LLM_MAX_BATCH_DOCUMENTS=1 INGEST_LLM_MAX_BATCH_CHARS=3000 INGEST_LLM_MAX_DOCUMENT_CHARS=3000 INGEST_LLM_PARALLEL_REQUESTS=3 .venv/bin/kb reset-ingest --raw data/raw --all-databases --no-start-databases --no-replay-staged`
  reached OpenCode Zen but failed with `401 CreditsError: Insufficient balance`.
- `[DONE]` Restored Unified Catalog from richest staged run after failed reset:
  `.venv/bin/kb reset-ingest --raw data/raw --catalog-only --no-start-databases --replay-staged`
  restored 393 catalog assets and 17 asset sets without LLM calls.
- `[DONE]` `.venv/bin/kb stats` after staged restore:
  Catalog=393, Graph=0, Vector=0, Document=0; engines reported Neo4j/Qdrant
  offline to the CLI. Structural Layer Mapping has 46 classified entities,
  `unclassified=0`.

## Current Data Snapshot

After cache-only ingestion (semantic analysis disabled) using the seeded corpus (`data/raw` + `corporate_structure_and_offerings.md`), projections were refreshed end-to-end:

| KB | Catalog | Graph | Vector | Document |
|----|---------|-------|--------|----------|
| business_model_kb | 105 | 105 | 105 | 0 |
| causality_kb | 14 | 13 | 14 | 14 |
| config_kb | 130 | 0 | 0 | 0 |
| document_kb | 34 | 0 | 34 | 34 |
| planning_kb | 17 | 17 | 0 | 0 |
| process_kb | 52 | 52 | 0 | 0 |
| qa_kb | 17 | 0 | 17 | 0 |
| rules_kb | 24 | 24 | 24 | 24 |
| **TOTAL** | **393** | **211** | **194** | **72** |

- Engines online: Neo4j=211 nodes, Qdrant=194 vectors, Document KB=72 rows.
- Catalog now includes new flows `flow.fl101` (“Diseñar Suite Everyday Banking”) and `flow.fl102` (“Orquestar FlexPay + ShieldGuard”), seeded from the corporate structure corpus addition.
- Universal ontology summary: 46 entities classified across layers, `unclassified=0` (see latest `kb stats`).

## Remaining TODO

### Completed This Session

- `[DONE]` EventBus wired: `emit_asset_status_change()` called in
  `transition_asset_set`, `deploy_asset_set`, and `_persist_catalog_node`.
  Both AssetSet and member asset transitions emit events.
- `[DONE]` `_projection_results` in `AssetCatalogStore` now queries the
  `deployments` table for real projection status instead of always returning
  `"scheduled"`.
- `[DONE]` Vector semantic search wired in CLI `kb_query`:
  `AssetSearchService` accepts optional `VectorSearchAdapter`;
  `build_asset_search_service()` creates `QdrantKnowledgeBaseVectorAdapter`;
  `kb_query` now returns real vector results instead of `"not_wired"`.
- `[DONE]` 9 inline editor plugins created (process, tool, qa, plan,
  user_task, document, configuration, module, form). Each follows the
  menu-editor plugin pattern: `components.js`, `helpers.js`, schema.json,
  ui-schema.json, `index.js`, `validators.test.js`.
- `[DONE]` `GenericPayloadView` removed from `AssetInlineEditor.tsx`;
  all 15 asset types now route to dedicated plugin editors.
- `[DONE]` Flow editor UI tests added (vitest + @testing-library/react):
  helpers validation + rendering test. Vitest configured in launcher.
- `[DONE]` Flow editor stays in `plugins/asset-editors/src/editors/flow-editor`
  (consistent with all other editors).
- `[DONE]` 104/104 editor unit tests, 99/99 Python tests, vitest 5/5,
  build clean, lint clean.
- `[DONE]` `kb-stats` command fixed: moved from `app/cli/__init__.py` to
  `app/platform_cli.py` (the actual `kb` CLI entry point). Fixed dead code
  from bad merge. Command registered as `kb stats` (table/JSON).
- `[DONE]` Universal ontology updated to enterprise layers (organization, capability, portfolio, offering, program, channel, transaction, agreement, event, metric, workforce, workforce_role); extraction schema + business_layer heuristics now align with workforce/role modeling.
- `[DONE]` CanonicalAssetPipeline now consumes ontology keywords from config instead of hard-coded banking strings; Settings + tooling/tests pass the ontology file so classification is fully data-driven.
- `[DONE]` Ontology search-space migration phase 1 implemented in contracts and backend compatibility:
  `semantic_space` added as governed search context; `structural_layer`
  is now the canonical entity classification emitted by ingest; legacy
  `business_layer` and `concept` are still accepted/read for migration.
- `[DONE]` `config/ontology/universal_layers.yaml` now owns the construction
  contract for semantic spaces, structural layers, entities, aliases,
  evidence, and relation families. Entity-to-entity facts remain graph
  relations; layers classify entities instead of storing facts.
- `[DONE]` Catalog and graph projections now persist/read
  `structural_layer`; Neo4j creates `StructuralLayer` nodes and
  `CLASSIFIES` edges for entity assets while preserving business relations
  between assets.
- `[DONE]` Ask asset search now indexes `structural_layer` and
  `semantic_space` metadata and traces matched structural layers/spaces in
  `asset_search` output.
- `[DONE]` `/catalog/knowledge-bases/{kb}/ontology` now returns
  `structural_layer` plus legacy `layer` compatibility for the launcher
  ontology canvas.
- `[DONE]` Ingestion LLM extraction can now run document batches in parallel:
  `CorpusFlowLoader` keeps small OpenCode Zen batches (`1` doc / `3k` chars)
  and defaults to `INGEST_LLM_PARALLEL_REQUESTS=3` for that provider. Results
  are merged in original batch order, while per-batch split/retry/skip behavior
  remains unchanged.
- `[DONE]` `.env.example` documents the reset/ingest performance knobs:
  `INTENT_LLM_TIMEOUT_SECONDS`, `INGEST_LLM_MAX_BATCH_DOCUMENTS`,
  `INGEST_LLM_MAX_BATCH_CHARS`, `INGEST_LLM_MAX_DOCUMENT_CHARS`, and
  `INGEST_LLM_PARALLEL_REQUESTS`.
- `[BLOCKED]` Full reset from raw is blocked by OpenCode Zen billing
  (`401 CreditsError: Insufficient balance`). Current local recovery restored
  the Unified Catalog from staged assets only; runtime graph/vector/document
  projections need a successful all-database ingest/reprojection after credits
  are available or another LLM provider is configured.

### Medium Priority (Remaining)

- `[DONE]` Complete ontology search-space migration (Phase 1 + Phase 2):
  - `[DONE]` Replay/reset ingest so persisted catalog, graph, and vector data carry
    `structural_layer` everywhere instead of relying on `business_layer`
    fallback. Neo4j: 509 nodes, 615 relationships. Qdrant: 300 points.
    Catalog: 558 assets. Document KB: 81 documents.
  - `[DONE]` Update launcher ontology editor copy/filter labels from layer/business
    layer to structural layer. Added `structural_layer` as canonical field,
    `layer` kept for backward compat. Added `semantic_space` field.
  - `[DONE]` Added `--format ontology-tree` CLI mode for hierarchical entity
    viewing grouped by structural_layer.
  - `[DONE]` Fixed `_asset_filename` truncation in staging.py (200 char max).
  - `[DONE]` Fixed `_parse_json_content` in llm_flow_loader.py to strip
    markdown code fences from LLM responses.
  - `[TODO]` Remove `entity_role` as a primary field after compatibility data is
    migrated.
  - `[TODO]` Retire `config/knowledge_base/concept_aliases.yaml` as an authority once
    governed entity aliases are fully sourced from catalog/graph.
  - `[TODO]` Keep `technical_type` scoped to `table` entities for now.
  - `[TODO]` Verify regenerated data no longer emits legacy structural layer `asset`;
    compatibility currently maps it to `business_resource`.
  - `[TODO]` Model structural sublevels such as `party.customer`,
    `party.prospect`, and `organization.department` as entity `subtype`
    values by default, not graph nodes or relationships.
  - `[TODO]` Keep table columns, identifiers, and ordinary attributes as entity
    properties instead of graph nodes.
  - `[TODO]` Continue wiring evidence JSON through assets, ask traces, and answers; do
    not introduce `evidence_bundle` as an asset type.
  - `[TODO]` Do not add `dimension`, `metric`, or `data_asset` asset types in the next
    phase.
  - `[TODO]` Use `docs/specs/ontology-search-spaces.md` as the implementation planning
    source for ingest and ask.

## Launcher Editor Architecture (Canonical)

### Stack

- React 19 + TypeScript 6 (Vite 8)
- JSON Forms (`@jsonforms/react` + `@jsonforms/vanilla-renderers`) for form rendering
- Zod (`zod@^3.25.76`) for client-side validation
- Inline styles with shared `colors` palette
- shadcn/ui (Radix UI + custom primitives)

### Plugin Pattern

Every asset editor MUST be a separate plugin under:
```
app/launcher/plugins/asset-editors/src/editors/<name>-editor/
├── index.js                    # Public exports
├── components.js               # React components (h() = React.createElement)
├── helpers.js                  # Zod schemas + normalizers + validators
├── <name>.schema.json          # JSON Schema for JSON Forms
├── <name>.ui-schema.json       # UI Schema for JSON Forms layout
└── validators.test.js          # Unit tests with Node.js test runner
```

### Editor Contract

Each editor receives `{ value, onChange, readOnly }` where `value` is the
full asset document. Editors must provide tabs: Structured Editor, Raw Source,
Relations, History.

### Existing Editors

| Editor | Status | Location |
|--------|--------|----------|
| `flow-editor` | Active (plugin) | `plugins/asset-editors/src/editors/flow-editor/` |
| `ontology-editor` | Active (plugin) | `plugins/asset-editors/src/editors/ontology-editor/` |
| `business-rule-editor` | Active (plugin) | `plugins/asset-editors/src/editors/business-rule-editor/` |
| `navigation-editor` | Active (plugin) | `plugins/asset-editors/src/editors/navigation-editor/` |
| `menu-editor` | Active (plugin) | `plugins/asset-editors/src/editors/menu-editor/` |
| `domain-editor` | Active (plugin) | `plugins/asset-editors/src/editors/domain-editor/` |
| `process-editor` | Active (plugin) | `plugins/asset-editors/src/editors/process-editor/` |
| `tool-editor` | Active (plugin) | `plugins/asset-editors/src/editors/tool-editor/` |
| `qa-editor` | Active (plugin) | `plugins/asset-editors/src/editors/qa-editor/` |
| `plan-editor` | Active (plugin) | `plugins/asset-editors/src/editors/plan-editor/` |
| `user-task-editor` | Active (plugin) | `plugins/asset-editors/src/editors/user-task-editor/` |
| `document-editor` | Active (plugin) | `plugins/asset-editors/src/editors/document-editor/` |
| `configuration-editor` | Active (plugin) | `plugins/asset-editors/src/editors/configuration-editor/` |
| `module-editor` | Active (plugin) | `plugins/asset-editors/src/editors/module-editor/` |
| `form-editor` | Active (plugin) | `plugins/asset-editors/src/editors/form-editor/` |

### Inline Editor Cleanup (Complete)

The following legacy code in `AssetInlineEditor.tsx` has been removed:
- `GenericPayloadView` - was fallback editor for 9 asset types. All now
  use dedicated plugin editors.
- `SourceEditor` (lines 152-212) - remains as fallback for unrecognized
  asset types (form_version, ruleset, concept, causality, asset_set).

### Legacy Cleanup

- `[DONE]` Deleted `pages/.lowdefy/` directory (entire legacy Lowdefy runtime)
- `[DONE]` Removed lowdefy gitignore entry from `.gitignore`
- `[DONE]` Removed `formSchema.ts` (legacy static form field definitions)
- `[DONE]` Removed legacy form types from `types.ts` (FormField, ModuleFormField, ModuleFormDefinition)

## Data Consistency Fixes (June 15, 2026)

### Root Causes Found and Fixed

1. **UserTask slug mismatch (35 catalog vs 52 Neo4j)**
   - `_flow_candidates` at `asset_pipeline.py:901` used `task.task` (short slug like `identificar_al_cliente`)
   - UserTask asset_id built from `task.name` (full slug like `identificar_al_cliente_antes_de_cualquier_operacion_financiera`)
   - Fix: Changed both `_flow_candidates` and `_record_relations_for_text` to use `task.name` first

2. **Flow graph projection dropped 17 flows (16 Neo4j vs 33 catalog)**
   - `user_task_refs` was a required field in `extraction_schema.yaml:251`
   - Named flows (customer-create, loan-payment, etc.) had no user tasks extracted by LLM
   - Fix: Moved `user_task_refs` from required to optional fields, set composition required=false

3. **Causality graph filter too strict (3 Neo4j vs 14 catalog)**
   - `_should_project_asset` at `neo4j.py:590` required BOTH `has_cause` AND `has_effect`
   - Each causality asset has only ONE relation (either cause or effect)
   - Fix: Changed `and` to `or` — project if EITHER relation exists

4. **Vector store severely under-populated (50 points vs 179 expected)**
   - `asset_types.yaml` only declared `vector` for `document` and `qa`
   - Topology defined vector collections for all 8 KBs
   - Fix: Added `vector` to entity, tool, user_task, business_rule, ruleset, causality, concept

### Final Store Counts

| KB | Catalog | Graph | Vector | Document |
|----|---------|-------|--------|----------|
| business_model_kb | 91 | 91 | 91 | 0 |
| causality_kb | 14 | 13 | 14 | 14 |
| config_kb | 128 | 0 | 0 | 0 |
| document_kb | 33 | 0 | 33 | 33 |
| planning_kb | 17 | 17 | 0 | 0 |
| process_kb | 50 | 50 | 0 | 0 |
| qa_kb | 17 | 0 | 17 | 0 |
| rules_kb | 24 | 24 | 24 | 24 |
| **TOTAL** | **374** | **195** | **179** | **71** |

### Remaining Minor Discrepancies
- causality: 14 catalog vs 13 graph — 1 asset has empty relations (LLM extraction quality issue)
- config_kb: 128 catalog, 0 elsewhere — correct by design (catalog/relational only)
- flow, process, plan: no vector — by design (semantic search not needed for executable assets)

## Ingestion Provider Compatibility (June 16, 2026)

- `[DONE]` Hardened OpenAI-compatible ingestion calls for OpenCode Zen
  (`https://opencode.ai/zen/v1`) in `app/ingestion/llm_flow_loader.py`.
- What changed:
  - `OpenAICompatibleLLMClient` now normalizes accidental
    `/chat/completions` suffixes from `OPENAI_BASE_URL`.
  - Default request headers are closer to the validated curl call:
    `User-Agent: curl/8.5.0`, `Accept: */*`, and JSON content type.
  - Headers are configurable through `OPENAI_COMPATIBLE_USER_AGENT`,
    `OPENAI_COMPATIBLE_ACCEPT`, and `OPENAI_COMPATIBLE_EXTRA_HEADERS`.
  - The OpenAI `response_format` field is disabled by default for OpenCode
    Zen to match the validated curl payload; `OPENAI_COMPATIBLE_RESPONSE_FORMAT`
    can explicitly override it.
  - LLM request logging records base URL, model, timeout, payload bytes,
    and non-secret headers while redacting authorization.
  - OpenCode Zen profile reduces ingestion request size to 1 document /
    3k chars per batch and chunks large text documents at 3k chars.
  - OpenCode Zen uses a compact text-only extraction prompt for text corpus
    documents because the full schema prompt and multimodal content-array
    shape caused long provider timeouts.
  - `403`, `1010`, and `Cloudflare` extraction errors now trigger the same
    split-and-retry path as timeouts and 413s; skipped fragments are retained
    in merged `_skipped` output for audit visibility.
- Why it changed:
  - Curl validation proved the key, endpoint, and model were valid.
    Failures during full no-cache ingestion were consistent with provider/WAF
    sensitivity to HTTP headers or large automated request payloads.
- Affected paths:
  - `app/ingestion/llm_flow_loader.py`
  - `tests/test_llm_flow_loader.py`
  - `docs/launcher/implementation-tracker.md`
- Affected command:
  - `./.venv/bin/kb reset-ingest --raw data/raw --all-databases --start-databases`
- Verification:
  - `[DONE]` `./.venv/bin/pytest -q tests/test_llm_flow_loader.py`
    (26 passed, 2 Qdrant insecure-connection warnings)
  - `[DONE]` `./.venv/bin/pytest -q tests/test_llm_flow_loader.py -k "opencode or timeout or cloudflare or batch"`
    (7 passed, 19 deselected)
- Remaining TODO/BLOCKED:
  - `[BLOCKED]` Full live OpenCode Zen no-cache ingest with
    `deepseek-v4-pro` was attempted multiple times on June 16, 2026 using the
    `opencode` key from `~/.local/share/opencode/auth.json`, not the stale
    OpenRouter `.env` key. Minimal curl-compatible calls work, and a single
    business document probe extracted assets successfully after simplifying
    the Zen prompt. The full command remains operationally blocked because
    the provider/model takes too long on the 34-document corpus with no cache.
  - `[DONE]` Stopped stale/long-running reset-ingest processes so no
    background ingestion remains active.
  - `[DONE]` Current post-reset `./.venv/bin/kb stats` shows empty KB state:
    Catalog=0, Graph=0, Vector=0, Document=0.
  - `[TODO]` Choose one recovery path: use a faster Zen model, allow staged or
    per-batch cache/checkpointing, or ingest a smaller raw subset before the
    full corpus.

## OpenCode Zen Model Selection (June 16, 2026)

- `[DONE]` Evaluated faster OpenCode Zen models for the live ingestion
  extraction path using `data/raw/process_examples_refinance.md` as a grounded
  probe document.
- Selected model:
  - `deepseek-v4-flash`
- Why:
  - It is the fastest successful open-source/open-weight-family candidate
    tested through Zen for this structured extraction task.
  - It returned valid normalized assets without `_skipped` output.
  - It was materially faster than `deepseek-v4-pro` and the other candidates
    tested for the same document/prompt path.
- Benchmark results:
  - `deepseek-v4-flash`: 36.26s, 4 flows, 6 tasks, no skipped fragments.
  - `deepseek-v4-flash-free`: 62.46s, 4 flows, 7 tasks, no skipped fragments.
  - `glm-5`: 71.17s, 4 flows, 6 tasks, no skipped fragments.
  - `kimi-k2.5`: 57.50s, 4 flows, 8 tasks, no skipped fragments.
  - `qwen3.6-plus`: timed out at 75s and returned skipped output.
  - `qwen3.6-plus-free`: unavailable; Zen returned 401 because the free
    promotion ended.
- Config changes:
  - `.env` now uses `OPENAI_BASE_URL=https://opencode.ai/zen/v1`.
  - `.env` now uses `INTENT_LLM_MODEL=deepseek-v4-flash`.
  - `.env.example` documents `OPENCODE_ZEN_API_KEY`, Zen base URL, and
    `deepseek-v4-flash`.
  - `app/config/settings.py` resolves the OpenCode Zen API key from
    `OPENCODE_ZEN_API_KEY` or `~/.local/share/opencode/auth.json` when Zen is
    configured and `.env` still contains an old OpenRouter key.
- Verification:
  - `[DONE]` `./.venv/bin/pytest -q tests/test_settings.py tests/test_llm_flow_loader.py -k "settings or opencode or timeout or cloudflare or batch"`
    (10 passed, 19 deselected)
  - `[DONE]` `./.venv/bin/python -m py_compile app/config/settings.py app/ingestion/llm_flow_loader.py`
  - `[DONE]` Live configured-path probe with `load_settings()` and
    `deepseek-v4-flash`: 40.35s, 4 flows, 8 tasks, no skipped fragments.
- Remaining TODO/BLOCKED:
  - `[TODO]` Re-run full no-cache `kb reset-ingest` with `deepseek-v4-flash`.
    It should be significantly faster than `deepseek-v4-pro`, but the full
    34-document corpus may still take substantial time without checkpointing.

## Current Load Verification (June 16, 2026)

- `[CHECKED]` User asked whether reset+ingest completed and what remains.
- Verification performed:
  - `./.venv/bin/kb stats`
  - Direct SQLite inspection of
    `data/processed/knowledge_base/asset_catalog.sqlite`
  - Direct SQLite inspection of
    `data/processed/knowledge_base/document_kb.sqlite`
- Current observed state in this workspace:
  - `kb stats` reports Catalog=0, Graph=0, Vector=0, Document=0.
  - `asset_catalog.sqlite` tables are present but empty:
    `assets=0`, `asset_sets=0`, `asset_versions=0`,
    `active_asset_sets=0`, `relationships=0`.
  - `document_kb.sqlite` has `documents=0`.
  - Latest audit files are still from earlier runs; no new completed
    `ingestion_run_*.json` was found for the claimed completed load.
- Config state:
  - `OPENAI_BASE_URL=https://opencode.ai/zen/v1`
  - `INTENT_LLM_MODEL=deepseek-v4-flash`
  - OpenCode Zen key resolves successfully from local auth rather than the old
    OpenRouter key.
- Remaining TODO/BLOCKED:
  - `[TODO]` Re-run or locate the completed ingest output. In the current
    workspace, the databases are empty after reset and are not loaded.
  - `[TODO]` Docker status check via `docker compose ps` failed because the
    installed Docker client API version is too old for the daemon
    (`client version 1.43`, daemon requires `1.44`), so container status could
    not be confirmed through that command.

## Full Reset And Ingest Completed (June 16, 2026)

- `[DONE]` Ran full no-cache reset+ingest with OpenCode Zen and
  `deepseek-v4-flash`:
  - `./.venv/bin/kb reset-ingest --raw data/raw --all-databases --start-databases --no-replay-staged`
- Runtime behavior:
  - Existing ingestion cache was deleted before the run.
  - `--no-replay-staged` ensured the run did not reuse staged extraction.
  - A transient Zen `500 Internal server error` was diagnosed and fixed by
    treating provider 5xx errors as retryable/skippable per document instead
    of aborting the whole ingest.
  - Generated ingestion cache was deleted after completion to preserve the
    requested no-cache state.
- Code changes:
  - `app/ingestion/llm_flow_loader.py` retryable markers now include provider
    5xx failures: `500`, `502`, `503`, `504`, internal server error, bad
    gateway, service unavailable, gateway timeout.
  - `tests/test_llm_flow_loader.py` covers provider 500 handling.
- Load summary:
  - status: `apply`
  - source_files: 34
  - flows_persisted: 84
  - user_tasks_extracted: 326
  - tools_extracted: 0
  - canonical_assets_generated: 784
  - catalog_assets_persisted: 784
  - audit:
    `data/processed/ingestion_audit/ingestion_run_20260616T185503Z.json`
- Verification:
  - `[DONE]` `./.venv/bin/pytest -q tests/test_llm_flow_loader.py -k "provider_500 or opencode or timeout or cloudflare or batch"`
    (8 passed, 19 deselected)
  - `[DONE]` `./.venv/bin/python -m py_compile app/ingestion/llm_flow_loader.py`
  - `[DONE]` `./.venv/bin/kb stats`
    - Neo4j: 543 nodes
    - Qdrant: 473 points
    - Catalog total: 772
    - Graph total: 543
    - Vector total: 473
    - Document total: 79
    - Combined total: 1867
  - `[DONE]` No `reset-ingest` process remains running.
  - `[DONE]` `data/processed/ingestion_cache` contains 0 cache files after
    cleanup.
- Remaining TODO/BLOCKED:
  - `[TODO]` Review generated audit and human-review artifact; audit reports
    `human_review.required=true`.

## Ontology Canvas Runtime Fix (June 16, 2026)

- `[DONE]` Diagnosed the ontology editor fetch error where the launcher showed
  an HTML response instead of JSON.
- Root cause:
  - `ontology-editor/components.js` used a relative fetch to
    `/catalog/knowledge-bases/{kb}/ontology?environment=dev`.
  - In the Vite dev server, that route resolves to `http://127.0.0.1:3000`
    and returns the frontend `index.html`.
  - FastAPI on `http://127.0.0.1:8030` returned JSON for the same API path.
- Fix:
  - `ontology-editor/components.js` now uses
    `VITE_LAUNCHER_API_URL ?? http://127.0.0.1:8030`, matching
    `app/launcher/src/api.ts`.
  - `app/api.py` ontology endpoint now uses the same manual knowledge-base
    filter as `/catalog/assets`, so owner/primary-KB catalog assets are
    included.
  - `app/api.py` ontology endpoint now includes inbound entity relationships
    via `AssetCatalogStore.find_referencers()`, not only outbound children.
  - `OntologySelection` and the right governance panel now distinguish
    incoming vs outgoing ontology relations.
- Verification:
  - `[DONE]` FastAPI endpoint:
    `GET http://127.0.0.1:8030/catalog/knowledge-bases/business_model_kb/ontology?environment=dev`
    returns `application/json`, `entity_count=60`, `relation_count=243`.
  - `[DONE]` Direct frontend host path still returns `text/html`, confirming
    the original failure mode and why the absolute API URL is required.
  - `[DONE]` `node --test app/launcher/plugins/asset-editors/src/editors/ontology-editor/validators.test.js`
    (4 passed)
  - `[DONE]` `npm --prefix app/launcher run build`
  - `[DONE]` `npm --prefix app/launcher run test:e2e -- --grep "business model"`
    (1 passed)
- Current runtime:
  - Vite launcher remains on `http://127.0.0.1:3000`.
  - FastAPI restarted and running on `http://0.0.0.0:8030`.

### Embedded Canvas Button Fix (June 16, 2026)

- `[DONE]` Fixed the runtime path where clicking `Editar ontología` on a
  knowledge-base node opened an entity editor but the canvas stayed blank or
  switched to the JSON Forms surface.
- Root causes:
  - `AssetInlineEditor.sourceDocument()` dropped the selected asset's KB
    context when the catalog detail payload already contained an `asset_id`.
  - Entity catalog details store the KB as payload `owner`, not always as
    top-level `primary_kb`; `knowledgeBaseFromDocument()` did not read the
    top-level `owner` field after normalization.
  - `App.tsx` passed React's state setter directly as the ontology form
    handler registrar. Registering a function made React execute it as a
    state updater, switching the editor to `Formulario` during render.
  - tldraw rejected hex colors in generated shape props; current tldraw
    expects named colors such as `grey`, `green`, `orange`, and `light-blue`.
- Fix:
  - `AssetInlineEditor.tsx` now preserves `primary_kb` when building the
    plugin document and passes `selected.primary_kb ?? selected.payload.owner`
    explicitly to `OntologyEditorView`.
  - `knowledgeBaseFromDocument()` now reads top-level `owner` and
    `knowledge_base` before falling back to payload fields or `catalog`.
  - `App.tsx` wraps ontology form handler registration in a stable
    `useCallback` and stores function handlers as state values instead of
    invoking them as updater functions.
  - `ontology-editor/components.js` now uses tldraw-supported color names for
    entity and relation shapes.
- Affected paths:
  - `app/launcher/src/App.tsx`
  - `app/launcher/src/components/AssetInlineEditor.tsx`
  - `app/launcher/plugins/asset-editors/src/editors/ontology-editor/components.js`
  - `app/launcher/plugins/asset-editors/src/editors/ontology-editor/helpers.js`
- Verification:
  - `[DONE]` Real Playwright browser run against Vite + FastAPI:
    clicking `Assets -> Editar ontología` requests
    `GET http://127.0.0.1:8030/catalog/knowledge-bases/business_model_kb/ontology?environment=dev`,
    renders the tldraw canvas, displays `business_model_kb`, shows 60 entity
    shapes, and updates the right governance panel to the selected `CBU`
    ontology node.
  - `[DONE]` Screenshot captured at
    `/tmp/ontology-real-after-color-fix.png`.
  - `[DONE]` `node --test app/launcher/plugins/asset-editors/src/editors/ontology-editor/validators.test.js`
    (4 passed)
  - `[DONE]` `npm --prefix app/launcher run build`
    (passed; Vite chunk-size warning only)
- Remaining TODO:
  - `[TODO]` Decide whether the canvas should render external asset nodes
    for inbound relations. Current data has 243 inbound relations from flows,
    rules, asset sets, etc.; the canvas intentionally draws only
    entity-to-entity arrows, so visible relation count is 0 while the right
    panel still lists inbound relations for the selected entity.

### Ontology Relation Visualization UX (June 17, 2026)

- `[DONE]` Updated the ontology canvas so relationships are visible in the
  launcher diagram, not only in the right governance panel.
- What changed:
  - `ontology-editor/components.js` now keeps relations where either endpoint
    is a visible entity and renders compact external asset nodes for non-entity
    endpoints such as `flow`, `business_rule`, `ruleset`, `asset_set`, `qa`,
    `plan`, and `process`.
  - The canvas now draws the live inbound relations from those external assets
    into ontology entities; the current `business_model_kb` run renders 243
    relation arrows plus external nodes.
  - tldraw's internal UI is hidden for the embedded read-only canvas so the
    launcher toolbar is the primary control surface.
  - Canvas zoom is explicit and stable: `+`, `-`, and `Ajustar vista` call
    tldraw zoom APIs, while automatic fit runs only once after graph load so
    manual zoom is not immediately reset.
  - Opening ontology from a KB or directly from an entity collapses the shell
    left and right sidebars to prioritize canvas space.
  - Large `Editar` / `Editar ontología` buttons were replaced by three-dot
    action menus in the asset header, KB rows, tree asset rows, and route rows.
- Affected paths:
  - `app/launcher/plugins/asset-editors/src/editors/ontology-editor/components.js`
  - `app/launcher/src/App.tsx`
  - `app/launcher/src/components/AssetExplorer.tsx`
  - `app/launcher/src/App.css`
- Verification:
  - `[DONE]` Real Playwright browser run against Vite + FastAPI:
    opened `Assets -> business_model_kb -> ... -> Canvas de ontología`,
    confirmed both shell sidebars collapsed, tldraw rendered 463 shapes
    including 243 relation arrows and 160 external asset nodes, and zoom
    buttons `+` / `-` were clickable without console errors.
  - `[DONE]` Screenshot captured at `/tmp/ontology-relations-final.png`.
  - `[DONE]` `node --test app/launcher/plugins/asset-editors/src/editors/ontology-editor/validators.test.js`
    (4 passed)
  - `[DONE]` `npm --prefix app/launcher run build`
    (passed; Vite chunk-size warning only)
- Remaining TODO:
  - `[TODO]` Consider adding relation-density controls if the full impact view
    feels too crowded for large KBs, for example per-entity focus, by asset
    type, or maximum external nodes per type.

### Ontology Search And Focus UX Fix (June 17, 2026)

- `[DONE]` Fixed the ontology sidebar interaction where searching/selecting an
  entity such as `prestamo` could leave the launcher blank or unstable.
- Root causes:
  - The sidebar search was used as a destructive canvas filter, so typing a
    term could remove most of the graph and make the visual state feel blank.
  - Selecting from the entity list notified the parent on every render, which
    could trigger React maximum-depth loops.
  - The previous manual camera-centering math could move the tldraw viewport
    away from the selected node.
  - Rendering all 243 relations by default made basic inputs wait for canvas
    stability on slower runs.
- Fix:
  - Search now behaves like a professional entity picker: it filters the
    sidebar result list only, shows match counts, and selecting a result clears
    the search and focuses the entity.
  - Layer chips now come from the actual loaded data and include `sin capa`
    instead of offering empty layer filters that blank the canvas.
  - Selection notification is guarded by a stable selection key so the right
    governance panel updates only when the selected entity/relation set
    actually changes.
  - Entity focusing now uses tldraw's own `select()` + `zoomToSelection()` API
    instead of manual camera calculations.
  - Relation rendering defaults to `Foco seleccionado`, showing relations for
    the current entity; `Ver todas` switches to `Impacto completo`, capped at
    90 visible relations to avoid freezing large KB diagrams.
- Affected path:
  - `app/launcher/plugins/asset-editors/src/editors/ontology-editor/components.js`
- Verification:
  - `[DONE]` Real Playwright browser run:
    opened `business_model_kb`, searched `prestamo`, selected the exact
    `prestamo` entity, confirmed the search cleared, the canvas did not show
    the empty-state message, no console/page errors appeared, focus mode
    rendered 45 relation arrows for the selected entity, and complete mode
    rendered 90 capped relation arrows without freezing.
  - `[DONE]` Screenshot captured at
    `/tmp/ontology-search-select-prestamo-centered.png`.
  - `[DONE]` `node --test app/launcher/plugins/asset-editors/src/editors/ontology-editor/validators.test.js`
    (4 passed)
  - `[DONE]` `npm --prefix app/launcher run build`
    (passed; Vite chunk-size warning only)

### Ontology Bound Connector Fix (June 17, 2026)

- `[DONE]` Fixed the ontology relationship lines so they behave like real
  diagram connectors instead of loose arrows.
- Root cause:
  - Relation arrows were created as independent tldraw arrow shapes with
    calculated start/end coordinates. They were visually close to the nodes,
    but not bound to the source and target shapes.
  - External relation nodes were laid out with a repeating modulo offset, so
    dense focus views could stack nodes and make connectors look unstable.
  - Relation labels rendered directly on every arrow, creating visual noise
    and overlap in high-density focus views.
- Fix:
  - `renderOntologyGraph()` now creates tldraw arrow bindings with
    `editor.createBindings()` for both `start` and `end` terminals, using
    `snap: "edge"` and normalized anchors. Arrows now stay attached to their
    source and target shapes as graph connectors.
  - External asset nodes are sorted and distributed into left/right columns
    around their anchor entity instead of reusing the same seven offsets.
  - Arrow labels were removed from the canvas lines; relation type remains
    available in the right governance panel and stats, keeping the diagram
    readable.
  - Entity focus now frames the full selected relationship neighborhood with
    `zoomToFit()` instead of zooming too tightly into a single node.
- Affected path:
  - `app/launcher/plugins/asset-editors/src/editors/ontology-editor/components.js`
- Verification:
  - `[DONE]` Real Playwright browser run:
    opened `business_model_kb`, searched and selected `prestamo`, confirmed
    45 bound relation arrows and 45 external relation nodes render without
    console errors or blank canvas state.
  - `[DONE]` Screenshot captured at
    `/tmp/ontology-bound-layout-prestamo-final.png`.
  - `[DONE]` `node --test app/launcher/plugins/asset-editors/src/editors/ontology-editor/validators.test.js`
    (4 passed)
  - `[DONE]` `npm --prefix app/launcher run build`
    (passed; Vite chunk-size warning only)

### MiMo-V2.5 Free + Full Ingestion (June 18, 2026)

- `[DONE]` Switched LLM to `mimo-v2.5-free` (fastest free Zen model: 23.7s vs
  31s for deepseek-v4-flash-free). Set `INTENT_LLM_MODEL=mimo-v2.5-free` in
  `.env`.
- `[DONE]` Fixed `_parse_json_content()` in `app/ingestion/llm_flow_loader.py`
  to strip markdown code fences from LLM responses (MiMo wraps JSON in ````json` blocks).
- `[DONE]` Fixed `_asset_filename()` in `app/ingestion/staging.py` to truncate
  filenames to 200 chars max (prevented `OSError: File name too long` on
  asset_sets with long IDs).
- `[DONE]` `reset-ingest --all-databases --start-databases` completed successfully.
  Source files: 34, flows: 49, user_tasks: 138, canonical_assets: 565.
- `[DONE]` Verified all stores populated:
  - Neo4j: 509 nodes, 615 relationships
  - Qdrant: 300 points (202 business_model + 14 causality + 34 document + 17 qa + 33 rules)
  - Document KB: 81 documents
  - Catalog: 558 assets
- `[DONE]` Added `--format ontology-tree` CLI mode to `app/cli/__init__.py`.
  Renders entities grouped by `structural_layer` as a rich tree.
- `[DONE]` Phase 2 ontology migration in launcher:
  - Added `STRUCTURAL_LAYERS` and `SEMANTIC_SPACES` exports to helpers.js
  - Added `structural_layer` as canonical entity field (backward compat with `layer`)
  - Added `semantic_space` field to entity schema
  - Updated `ontology-editor.schema.json` with all structural layers and semantic spaces
  - Updated canvas rendering to prefer `structural_layer` over `layer`
  - Updated filter/sorting to use `structural_layer`
  - `index.js` exports updated
  - Build passes. Vite chunk-size warning only.
- Verification:
  - `[DONE]` `./.venv/bin/python -m app.platform_cli stats` shows all stores populated
  - `[DONE]` `./.venv/bin/python -m app.platform_cli query --owner-kb business_model_kb --format ontology-tree` renders tree
  - `[DONE]` Neo4j bolt query confirms 509 nodes, 615 relationships
  - `[DONE]` Qdrant confirms 300 points across 5 collections
  - `[DONE]` `npm --prefix app/launcher run build` passes
