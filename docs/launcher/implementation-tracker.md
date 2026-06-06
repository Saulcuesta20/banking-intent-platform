# Launcher Implementation Tracker

## Purpose

This document keeps the working context, decisions, completed work, and pending
tasks for the Enterprise AI Launcher. It is intended for developers joining the
project midstream so they can continue without rediscovering the architecture.

## Status Legend

- `[DONE]`: implemented and verified.
- `[IN_PROGRESS]`: implementation started but not complete.
- `[TODO]`: not started.
- `[BLOCKED]`: blocked by a decision, dependency, or missing contract.

## Current Architecture

The launcher has two UI runtimes:

- React/shadcn owns the shell, navigation, three-panel layout, chat, context
  panel, collapse/resizing behavior, and launcher-level state.
- Lowdefy owns dynamic catalog/editor screens and will own dynamically bound
  task forms once the flow-to-form binding contract exists.

The launcher runtime source of truth is the Unified Catalog exposed by FastAPI.
The launcher should not query Neo4j, Qdrant, or YAML files directly at runtime.

```text
AssetSet YAML files
  -> ingest/load
  -> Unified Catalog
  -> deployment
  -> KB projections: graph, vector, document, repository, relational
  -> React launcher and Lowdefy query FastAPI
```

## Key Decisions

- Domain, module, menu, submenu, form, and form-version are configurable
  launcher/catalog assets.
- Flow, process, business rule, QA, entity/concept, ontology, tool, and related
  semantic assets are knowledge assets projected to their configured KBs.
- AssetSet and AssetBundle are treated as the same deployment unit in this
  project vocabulary.
- An AssetSet is the deployment boundary, not an individual loose asset file.
- Existing AssetSet versions are immutable. Editing creates a new version.
- The launcher chat calls `app/ask` through FastAPI. There is no launcher-side
  fallback routing or hardcoded flow selection.
- Flow-to-form binding remains a second-stage design task.

## Runtime Locations

| Area | Path / URL |
|---|---|
| Launcher React app | `app/launcher/src` |
| Lowdefy generated YAML | `app/launcher/lowdefy-runtime/lowdefy.yaml` and `app/launcher/lowdefy-runtime/pages/*.yaml` |
| Lowdefy generator | `app/launcher/scripts/generate-lowdefy.mjs` |
| Lowdefy asset editor plugin | `app/launcher/lowdefy-plugins/asset-editors` |
| Asset editor integration plan | `docs/launcher/asset-editor-integration-plan.md` |
| AssetSet source folders | `app/launcher/modules/<module>/assetsets/<set>/` |
| Launcher docs | `docs/launcher/` and `app/launcher/docs/` |
| React launcher URL | `http://localhost:3000` |
| Lowdefy runtime URL | `http://localhost:3002` technical runtime only; users enter through the launcher |
| FastAPI URL | `http://127.0.0.1:8030` |

## Implemented Work

- `[DONE]` React launcher shell using shadcn-style components.
- `[DONE]` Three-panel launcher layout with left navigation, chat workspace, and
  right context panel.
- `[DONE]` Chat sends questions to FastAPI `/ask` and does not route locally.
- `[DONE]` Ask trace is displayed as step/result data in the launcher.
- `[DONE]` Asset sidebar option added to browse the Unified Catalog.
- `[DONE]` Asset tree/route view by KB, AssetSet, domain, module, and asset.
- `[DONE]` Asset filters by name, KB, asset type, status, and tag.
- `[DONE]` AssetSet lifecycle implemented:
  `draft -> ready_for_review -> in_review -> validated -> active`.
- `[DONE]` AssetSet deployment projects assets to configured KBs.
- `[DONE]` Lowdefy asset editors are embedded into the launcher
  domain/module/menu experience. React owns the shell; Lowdefy renders the
  selected editor body only.
- `[DONE]` Custom Lowdefy blocks implemented:
  `AssetCodeEditor`, `ProcessCanvas`, `OntologyGraph`, `RuleBuilder`,
  `FormDesigner`, `NavigationTree`, `AssetStudio`.
- `[DONE]` Launcher-native Lowdefy editor blocks exposed:
  `AssetEditorHost`, `FlowEditor`, `ProcessEditor`, `BusinessRuleEditor`,
  `OntologyEditor`, `QaEditor`, `EntityEditor`, `ToolApiEditor`,
  `FormAssetEditor`, `ModuleMenuEditor`, and `DocumentConfigEditor`.
- `[DONE]` Independent Lowdefy YAML pages generated for each editor under
  `app/launcher/lowdefy-runtime/pages/`.
- `[DONE]` Lowdefy editors can switch between visual mode and YAML/JSON source.
- `[DONE]` Editor validation calls FastAPI `/catalog/assets/validate`.
- `[DONE]` Editor save creates a new immutable AssetSet version through
  `/catalog/assets/{asset_id}/versions`.
- `[DONE]` Documentation updated for module runtime and Lowdefy editor plugin.
- `[DONE]` Architecture correction requested: Asset administration now
  reuse the launcher shell, domain dropdown, top module menu, left navigation,
  and right detail panel. Lowdefy should render the dynamic editor surface
  inside the launcher workspace only.
- `[IN_PROGRESS]` Detailed migration plan created in
  `docs/launcher/asset-editor-integration-plan.md`.

## FastAPI Endpoints In Scope

| Endpoint | Purpose |
|---|---|
| `POST /ask` | Resolve a user question through AskService and return trace steps. |
| `GET /launcher/home` | Build launcher home/navigation from active catalog assets. |
| `GET /launcher/flows/{flow_id}` | Return selected flow context. |
| `GET /catalog/metadata` | Return asset types, KBs, statuses, tags, domains, modules. |
| `GET /catalog/assets` | List catalog assets with filters and tree data. |
| `GET /catalog/assets/{asset_id}` | Return one catalog asset version. |
| `POST /catalog/assets/validate` | Validate edited asset document against registry and identity rules. |
| `POST /catalog/assets/{asset_id}/versions` | Create a new immutable AssetSet version from an edited asset. |
| `GET /catalog/asset-sets` | List AssetSet versions. |
| `GET /catalog/asset-sets/{asset_set_id}/{version}` | Return AssetSet detail. |
| `POST /catalog/asset-sets/{asset_set_id}/transition` | Move AssetSet through guarded lifecycle states. |
| `POST /catalog/asset-sets/{asset_set_id}/deploy` | Deploy a validated AssetSet. |
| `POST /catalog/asset-sets/{asset_set_id}/rollback` | Roll back an active AssetSet. |

## Pending Tasks

### Phase 1: Stabilize Asset Studio

- `[DONE]` Replace the standalone `AssetStudio` user experience with a
  launcher-native `Asset Management` domain/module. Lowdefy remains the editor
  runtime, but React owns the shell and perspective.
- `[DONE]` Refactor current monolithic
  `app/launcher/lowdefy-plugins/asset-editors/blocks.js` into independent
  editor files under `src/blocks`.
- `[DONE]` Generate independent Lowdefy YAML pages/fragments for each editor:
  flow, process, rule, ontology, QA, entity, tool/API, form, module/menu, and
  document/config.
- `[DONE]` Add an `asset-management` domain to the launcher
  domain dropdown.
- `[DONE]` Add modules/menus for asset administration:
  `Assets`, `Knowledge Bases`, `AssetSets`, and `Review Queue`.
- `[DONE]` Replace the current `AssetExplorer` iframe tab with an embedded
  Lowdefy editor panel that receives selected asset context from React.
- `[DONE]` Split the current monolithic `AssetStudio` Lowdefy block into smaller
  reusable editor blocks that fit inside the launcher workspace and right detail
  panel.
- `[DONE]` Keep asset list/tree/filter controls visually aligned with the
  launcher reference layout, not the standalone Lowdefy studio layout.
- `[TODO]` Add automated tests for the new FastAPI editor endpoints:
  `/catalog/assets/validate` and `/catalog/assets/{asset_id}/versions`.
- `[TODO]` Add Playwright smoke tests for Lowdefy Asset Studio:
  select each editor type, validate, and confirm no console errors.
- `[TODO]` Add a confirmation dialog before `Save new version`.
- `[TODO]` Add a typed version input option for manual version numbers.
- `[TODO]` Add visible diff preview between current version and edited draft.
- `[TODO]` Show lifecycle and deployment history inside the Lowdefy Asset Studio
  detail panel, not only in React context panel.
- `[TODO]` Normalize duplicate tags during AssetSet load and edit save.
- `[TODO]` Decide whether `v1` form versions should stay as `v1` or be migrated
  to semver like `1.0.0`.

### Phase 2: Flow-To-Form Binding

- `[BLOCKED]` Define `TaskFormBinding` contract.
- `[BLOCKED]` Decide whether binding lives on `flow`, `process`, `user_task`, or
  a separate `task_form_binding` asset type.
- `[TODO]` Design how process nodes/user tasks map to Lowdefy form pages.
- `[TODO]` Define how form state binds to process execution payload.
- `[TODO]` Implement dynamic form rendering from active Unified Catalog assets.
- `[TODO]` Ensure AskService returns selected flow/process only; the launcher
  should use catalog/binding metadata to decide which form to open.

### Phase 3: Knowledge Base And Deployment Governance

- `[TODO]` Add projection health status to Asset Studio after deployment.
- `[TODO]` Expose per-KB projection details for graph/vector/document stores.
- `[TODO]` Add a deployment preview step before activating an AssetSet.
- `[TODO]` Add rollback UI inside Lowdefy Asset Studio.
- `[TODO]` Add audit trail filters by actor, asset, AssetSet, and environment.
- `[TODO]` Add Git commit metadata capture on AssetSet version creation.

### Phase 4: Editor Quality

- `[TODO]` Replace the simple code textarea with Monaco or a richer code editor.
- `[TODO]` Upgrade `ProcessCanvas` to a true graph/canvas editor.
- `[TODO]` Upgrade `OntologyGraph` to an interactive node-edge graph.
- `[TODO]` Improve `RuleBuilder` with nested groups and AND/OR composition.
- `[TODO]` Improve `FormDesigner` with field-level validation editors.
- `[TODO]` Improve `NavigationTree` with nested submenu editing.

### Phase 5: Launcher Product Polish

- `[TODO]` Add profile/settings dropdown behavior matching the shadcn-admin
  reference.
- `[TODO]` Add domain/module breadcrumb synchronization with selected asset.
- `[TODO]` Add contextual actions in the right panel for selected asset and Ask
  result.
- `[TODO]` Improve empty/loading/error states across React and Lowdefy views.
- `[TODO]` Add role-based permissions for review, validation, deployment, and
  rollback actions.

## Open Questions

- Should asset lifecycle be tracked only at AssetSet level, or also visible as
  independent asset lifecycle events?
- Should forms use `form` plus `form_version`, or should each immutable form
  version be the deployable asset?
- Should Lowdefy generated YAML be committed, or regenerated only in build/dev?
- Should Lowdefy editor blocks be mounted through an iframe route with selected
  asset query parameters, or should they be wrapped as React components and
  rendered directly inside the launcher?
- Which KB should own ontology changes: graph only, or graph plus vector for
  semantic retrieval?

## Verification Commands

## Latest Verification

- `[DONE]` `npm run generate:lowdefy`
- `[DONE]` `npm run lint`
- `[DONE]` `npm run build`
- `[DONE]` `.venv/bin/pytest -q tests/test_asset_set_lifecycle.py tests/test_asset_registry.py tests/test_knowledge_graph.py`
- `[DONE]` HTTP smoke:
  `GET http://127.0.0.1:8030/catalog/metadata?environment=dev`,
  `GET http://127.0.0.1:3000/`,
  `GET http://127.0.0.1:3002/asset-flow-editor?asset_id=flow.loan.refinance&version=1.0.0`
- `[DONE]` Playwright smoke:
  domain `Asset Management` opens in the launcher, selecting a flow opens one
  `iframe.asset-editor-frame`, right panel remains `Asset Governance`, and no
  browser console errors were reported.

Run backend tests:

```bash
.venv/bin/pytest -q tests/test_asset_set_lifecycle.py tests/test_asset_registry.py tests/test_knowledge_graph.py
```

Run launcher checks:

```bash
cd app/launcher
npm run lint
npm run build
```

Run local services:

```bash
.venv/bin/uvicorn app.api:create_app --factory --host 127.0.0.1 --port 8030
cd app/launcher && npm run dev
```

## Handoff Notes

- Do not add launcher-side hardcoded routing for Ask results.
- Do not edit active AssetSet versions in place.
- Do not make React or Lowdefy read Neo4j, Qdrant, or YAML directly at runtime.
- Use the Unified Catalog API as the launcher runtime source of truth.
- Keep code and folder names in English.
- Keep user-facing Spanish labels where the business UX needs Spanish.
