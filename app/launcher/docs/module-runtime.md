# Launcher Module Runtime

## Runtime Boundary

The launcher has one browser runtime:

- React/shadcn owns the shell, navigation, three-panel layout, chat, trace,
  catalog explorer, and right context panel.

The Unified Catalog is the launcher source of truth. The browser queries
FastAPI only; it does not read Neo4j, Qdrant, or YAML files directly.

## Module Registry

Launcher module metadata is generated from:

```text
app/launcher/modules/<domain>/<module>/
```

using:

```bash
npm run generate:module-registry
```

That writes:

```text
app/launcher/public/module-registry.json
```

## Asset Editors

The active editor pattern is:

```text
JSON Schema
-> JSON Forms
-> Zod
-> FastAPI asset contract validation
-> Unified Catalog draft version
```

The reference implementation is the flow editor:

```text
app/launcher/plugins/asset-editors/src/editors/flow-editor/
```

## Assets Workspace

The sidebar `Assets` option provides:

- tree view by Catalog and AssetSet
- route view by domain/module/AssetSet/asset
- launcher-embedded asset editor view
- filters by name, type, status, and tag
- canonical asset properties and relationships
- human review actions
- deployment and lifecycle history

The browser shows the governed catalog view. Projection metadata may still be
visible in asset detail, but the editable record is always the Unified Catalog
entry.

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

Review and deployment are performed per AssetSet version, never per loose file.

## Deployment

Deployment performs these steps:

1. Verify the AssetSet is validated.
2. Load exact member versions from Unified Catalog.
3. Project each member to the configured backend stores.
4. Abort activation if a required projection fails.
5. Atomically update the active AssetSet pointer for the environment.
6. Record deployment metadata and lifecycle events.

Rollback reactivates the previous deployed AssetSet version.
