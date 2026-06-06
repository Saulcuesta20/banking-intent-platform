# Launcher Module Runtime

## Runtime Boundary

The launcher has two UI runtimes:

- React/shadcn owns the shell, navigation, three-panel layout, chat, trace, and context panel.
- Lowdefy owns declarative catalog screens, asset editors, and, in phase two,
  dynamically bound forms.

The Unified Catalog is the launcher source of truth. React and Lowdefy query
FastAPI; neither runtime reads repository files or Neo4j directly.

## AssetSet Authoring

Launcher assets are authored under:

```text
app/launcher/modules/<module>/assetsets/<set-name>/
  asset-set.yaml
  assets/
    <asset>.yaml
```

Each AssetSet declares:

- immutable id and version
- domain and module metadata
- one primary asset type
- exact member files
- tags and Git metadata

Export the original launcher JSON definitions once with:

```bash
.venv/bin/python -m app.launcher_cli assets export
```

Register AssetSet versions for review with:

```bash
.venv/bin/python -m app.launcher_cli assets load
```

## Lifecycle

```text
draft
-> ready_for_review
-> in_review
-> validated | rejected | draft
-> active
-> deprecated
-> retired
```

Review and deployment are available from the launcher `Assets` workspace.
Deployment is performed per AssetSet version, never per loose file.

## Deployment

Deployment performs these steps:

1. Verify the AssetSet is validated.
2. Load the exact member versions from Unified Catalog.
3. Project each member to its configured knowledge stores.
4. Abort activation if a required projection fails.
5. Atomically update the active AssetSet pointer for the environment.
6. Record the previous version, actor, checksum, projections, and timestamp.

Rollback reactivates the previous deployed AssetSet version.

## Assets Workspace

The sidebar `Assets` option provides:

- tree view by KB projection and AssetSet
- route view by domain/module/AssetSet/asset
- launcher-embedded Lowdefy editor view
- name, KB, type, status, and tag filters
- canonical asset properties and relationships
- human review actions
- deployment and lifecycle history

The tree shows projections. The editable canonical record always lives in the
Unified Catalog.

Lowdefy still runs on its own technical port, but users enter through the
launcher. The center workspace iframes one focused editor page for the selected
asset, not a standalone studio shell.

Editor routing is driven by `asset_type`:

| Asset types | Lowdefy page | Lowdefy editor |
|---|---|
| `flow` | `asset-flow-editor` | `FlowEditor` |
| `process` | `asset-process-editor` | `ProcessEditor` |
| `business_rule`, `rule`, `ruleset` | `asset-business-rule-editor` | `BusinessRuleEditor` |
| `form` | `asset-form-editor` | `FormAssetEditor` |
| `ontology`, `relationship` | `asset-ontology-editor` | `OntologyEditor` |
| `entity`, `concept` | `asset-entity-editor` | `EntityEditor` |
| `qa`, `question_answer` | `asset-qa-editor` | `QaEditor` |
| `tool`, `api`, `tool_api` | `asset-tool-api-editor` | `ToolApiEditor` |
| `domain`, `module`, `menu`, `submenu`, `navigation` | `asset-module-menu-editor` | `ModuleMenuEditor` |
| `document`, `configuration`, `config` | `asset-document-config-editor` | `DocumentConfigEditor` |
| all other types | `asset-code-editor` | `AssetCodeEditor` |

All editors can switch to the canonical YAML/JSON source view.

## Lowdefy

`npm run generate:lowdefy` generates:

```text
app/launcher/lowdefy-runtime/lowdefy.yaml
app/launcher/lowdefy-runtime/pages/*.yaml
```

The generated editor pages call:

```text
GET /catalog/assets/{asset_id}
POST /catalog/assets/validate
POST /catalog/assets/{asset_id}/versions
```

Saving from Lowdefy creates a new AssetSet version in:

```text
app/launcher/modules/<module>/assetsets/<set>/versions/<version>/
```

The new version enters `ready_for_review`. Lowdefy exposes the guarded
`start_review`, `validate`, `request_changes`, and deployment operations.

Form binding remains phase two. No launcher-side flow-to-form hardcoding should
be added before the `TaskFormBinding` contract is implemented.
