# Launcher-Native Asset Editor Integration Plan

## Goal

Move asset editing from a standalone `AssetStudio` page into the launcher shell.
The user should experience asset editing as another launcher domain/module, not
as a separate Lowdefy application.

The target visual model matches the provided editor mockups:

- same DevBank top navigation
- same left navigation sidebar
- same domain selector and top menu
- same center workspace
- same right `Asset Governance` panel
- same footer/status bar
- Lowdefy renders only the dynamic editor surface

## Original Problem

The previous implementation had the editor logic inside one Lowdefy plugin file:

```text
app/launcher/lowdefy-plugins/asset-editors/blocks.js
```

The block exports are:

```text
AssetCodeEditor
ProcessCanvas
OntologyGraph
RuleBuilder
FormDesigner
NavigationTree
AssetStudio
```

The generated Lowdefy runtime currently mounts a standalone page:

```text
app/launcher/lowdefy-runtime/lowdefy.yaml
```

with:

```yaml
asset-explorer -> AssetStudio
```

React then embedded that page with an iframe in:

```text
app/launcher/src/components/AssetExplorer.tsx
```

That technically worked, but visually and architecturally it behaved like a
separate application/perspective. That is not the desired launcher experience.

## Implemented Correction

The launcher now uses an `Asset Management` domain. React owns the same shell,
navigation, right governance panel, footer, selected asset state, filters, tree,
and route view. Lowdefy renders only the selected editor body through
`AssetEditorHost`.

Lowdefy editor pages are generated per asset type:

```text
app/launcher/lowdefy-runtime/pages/
  asset-flow-editor.yaml
  asset-process-editor.yaml
  asset-business-rule-editor.yaml
  asset-ontology-editor.yaml
  asset-qa-editor.yaml
  asset-entity-editor.yaml
  asset-tool-api-editor.yaml
  asset-form-editor.yaml
  asset-module-menu-editor.yaml
  asset-document-config-editor.yaml
  asset-code-editor.yaml
```

The old `AssetStudio` block remains only as a compatibility export. It is not
used as the launcher user experience.

## Target Architecture

### Launcher Shell

React/shadcn continues to own:

- top header
- domain selector
- top module menu
- left navigation
- center workspace layout
- right detail/governance panel
- footer/status bar
- selected asset state
- catalog browsing state

### Lowdefy Runtime

Lowdefy owns only the dynamic editor body:

- flow editor structured fields
- process canvas/editor
- business rule builder
- ontology graph/editor
- form designer
- QA editor
- entity editor
- tool/API editor
- module/menu editor
- document/config editor
- raw YAML editor
- compare/diff panel when rendered dynamically

### FastAPI / Unified Catalog

FastAPI remains the boundary for:

- asset search
- asset detail
- validation
- draft version creation
- lifecycle transition
- deployment
- rollback
- projection preview

## Proposed Launcher Domain

Add a launcher domain:

```text
asset-management
```

Suggested label:

```text
Asset Management
```

Suggested description:

```text
Govern knowledge bases, assets, AssetSets, editors, review, and deployments.
```

This domain appears in the existing domain dropdown.

## Proposed Modules And Menus

### Domain: Asset Management

| Module | Purpose | Top menu behavior |
|---|---|---|
| `assets` | Browse and edit catalog assets | Opens asset tree/list and editor workspace |
| `knowledge-bases` | View KBs and projections | Shows graph/vector/document/repository views |
| `asset-sets` | Review deployable bundles | Shows AssetSet versions and lifecycle |
| `review-queue` | Human validation queue | Shows items in `ready_for_review` and `in_review` |
| `deployments` | Deployment history and rollback | Shows active versions and deployment results |
| `ontology` | Browse/edit semantic model | Opens ontology editor |
| `rules` | Browse/edit business rules | Opens rule editor |
| `forms` | Browse/edit form definitions | Opens form designer |

Default top menus for this domain:

```text
Overview
Editors
Review
Deployments
Settings
```

## Editor File Organization

The current single `blocks.js` should be split into independent block files.

Target structure:

```text
app/launcher/lowdefy-plugins/asset-editors/
  package.json
  blocks.js
  metas.js
  types.js
  src/
    shared/
      editor-frame.js
      editor-state.js
      styles.js
      yaml-source.js
      catalog-client.js
    blocks/
      AssetCodeEditor.js
      FlowEditor.js
      ProcessEditor.js
      BusinessRuleEditor.js
      OntologyEditor.js
      QaEditor.js
      EntityEditor.js
      ToolApiEditor.js
      FormDesigner.js
      ModuleMenuEditor.js
      DocumentConfigEditor.js
```

`blocks.js` should only export block registrations:

```js
export { default as AssetCodeEditor } from './src/blocks/AssetCodeEditor.js'
export { default as FlowEditor } from './src/blocks/FlowEditor.js'
export { default as ProcessEditor } from './src/blocks/ProcessEditor.js'
export { default as BusinessRuleEditor } from './src/blocks/BusinessRuleEditor.js'
export { default as OntologyEditor } from './src/blocks/OntologyEditor.js'
export { default as QaEditor } from './src/blocks/QaEditor.js'
export { default as EntityEditor } from './src/blocks/EntityEditor.js'
export { default as ToolApiEditor } from './src/blocks/ToolApiEditor.js'
export { default as FormDesigner } from './src/blocks/FormDesigner.js'
export { default as ModuleMenuEditor } from './src/blocks/ModuleMenuEditor.js'
export { default as DocumentConfigEditor } from './src/blocks/DocumentConfigEditor.js'
```

The old `AssetStudio` block is no longer mounted by the generated Lowdefy
runtime. It can be deleted after any external references are removed.

## Lowdefy YAML Organization

Each editor should have a Lowdefy page or YAML fragment generated explicitly.

Target structure:

```text
app/launcher/lowdefy-runtime/
  lowdefy.yaml
  pages/
    asset-flow-editor.yaml
    asset-process-editor.yaml
    asset-business-rule-editor.yaml
    asset-ontology-editor.yaml
    asset-qa-editor.yaml
    asset-entity-editor.yaml
    asset-tool-api-editor.yaml
    asset-form-editor.yaml
    asset-module-menu-editor.yaml
    asset-document-config-editor.yaml
```

Each YAML page should render only an editor body, not a full application shell.

Example:

```yaml
- id: asset-flow-editor
  type: Box
  blocks:
    - id: flow_editor
      type: FlowEditor
      properties:
        apiBaseUrl: http://127.0.0.1:8030
        environment: dev
```

React can iframe the specific Lowdefy editor route inside the center workspace,
passing selected asset context by URL:

```text
http://localhost:3002/asset-flow-editor?asset_id=flow.loan.refinance&version=1.0.0
```

This is acceptable as a technical runtime detail as long as the visible shell is
the launcher, not the Lowdefy page.

## Launcher UI Target

The launcher page should look like:

```text
Topbar:
  DevBank | Domain: Asset Management | Overview | Editors | Review | Deployments | Settings

Left sidebar:
  General
    Dashboard
    Tasks
    Apps
    Chats
    Users
    Assets
  Modules
    Knowledge Bases
    Assets
    AssetSets
    Rules
    Processes
    Forms
    Ontology
    Deployments

Center workspace:
  Breadcrumb: Assets / Flows / loan.refinance
  Title: Edit Loan Refinance
  Status banner: Editing new draft version 1.1.0
  Tabs:
    Overview
    Structured Editor
    Relationships
    Raw YAML
    Compare Versions
  Lowdefy editor body
  Bottom validation/action bar

Right panel:
  Asset Governance
  AssetSet
  Current version
  Draft version
  Environment
  Git commit
  KB Projection Preview
  Deployment Impact
```

## Editor Mapping

| Asset type | Editor block | Lowdefy page |
|---|---|---|
| `flow` | `FlowEditor` | `asset-flow-editor` |
| `process` | `ProcessEditor` | `asset-process-editor` |
| `business_rule`, `ruleset` | `BusinessRuleEditor` | `asset-business-rule-editor` |
| `ontology` | `OntologyEditor` | `asset-ontology-editor` |
| `qa` | `QaEditor` | `asset-qa-editor` |
| `entity`, `concept` | `EntityEditor` | `asset-entity-editor` |
| `tool` | `ToolApiEditor` | `asset-tool-api-editor` |
| `form`, `form_version` | `FormAssetEditor` | `asset-form-editor` |
| `domain`, `module`, `menu`, `submenu` | `ModuleMenuEditor` | `asset-module-menu-editor` |
| `document`, `configuration` | `DocumentConfigEditor` | `asset-document-config-editor` |
| fallback | `AssetCodeEditor` | `asset-code-editor` |

## Implementation Tasks

### Phase A: Refactor Editors

- `[DONE]` Split `blocks.js` into independent editor files.
- `[DONE]` Rename current generic editors to domain-specific editor names:
  `ProcessCanvas` -> `ProcessEditor`, `RuleBuilder` -> `BusinessRuleEditor`,
  `NavigationTree` -> `ModuleMenuEditor`.
- `[DONE]` Add missing editor blocks:
  `FlowEditor`, `QaEditor`, `EntityEditor`, `ToolApiEditor`,
  `DocumentConfigEditor`.
- `[DONE]` Keep shared code in `src/shared`.
- `[DONE]` Remove user-facing dependency on `AssetStudio`.

### Phase B: Lowdefy YAML Pages

- `[DONE]` Generate independent Lowdefy YAML pages per editor.
- `[DONE]` Add query parameter support for `asset_id`, `version`, `environment`.
- `[DONE]` Each page loads only one selected asset and renders the matching
  editor body.
- `[DONE]` Do not render Lowdefy top navigation or a complete studio shell.

### Phase C: Launcher Integration

- `[DONE]` Add `asset-management` domain to launcher catalog/domain source.
- `[DONE]` Add asset management modules and menus.
- `[DONE]` Remove the `Lowdefy` tab from the current `AssetExplorer`.
- `[DONE]` Replace the current `asset-explorer` iframe with editor-specific
  Lowdefy iframe in the center workspace.
- `[DONE]` Preserve the right `Asset Governance` panel in React.
- `[IN_PROGRESS]` Add breadcrumb, status banner, tabs, bottom action bar, and
  compare preview matching the mockups. Breadcrumb, banner, tabs, and action
  buttons exist; richer compare preview remains pending.

### Phase D: Backend Support

- `[TODO]` Add endpoint for projection preview by asset/version.
- `[TODO]` Add endpoint for version diff.
- `[TODO]` Add endpoint for draft metadata preview before save.
- `[TODO]` Add tests for editor save/validate/diff/projection preview.

### Phase E: Verification

- `[TODO]` Add Playwright screenshots for each editor route.
- `[TODO]` Verify desktop and mobile layouts.
- `[TODO]` Verify no console errors.
- `[TODO]` Verify saved draft versions appear in review queue.
- `[TODO]` Verify active deployed version remains unchanged until deployment.

## Non-Goals For This Step

- Do not implement flow-to-form binding yet.
- Do not make Ask select forms directly.
- Do not make the launcher query YAML/Neo4j/Qdrant directly.
- Do not let Lowdefy own the global launcher shell.

## Documentation Updates Required While Implementing

Update these files whenever a phase changes:

```text
docs/launcher/implementation-tracker.md
docs/launcher/architecture.md
docs/launcher/components.md
app/launcher/docs/module-runtime.md
```

Use `[DONE]`, `[IN_PROGRESS]`, `[TODO]`, and `[BLOCKED]` consistently.
