# Enterprise AI Launcher

> Superseded product notes were consolidated. The current launcher
> architecture lives under `docs/launcher/`.

## Current Decision

The launcher is a React + TypeScript application in `app/launcher/` using
shadcn/ui patterns for the shell and FastAPI for all runtime integration.

The current front-end split is:

- React/shadcn owns navigation, three-panel layout, routing, chat workspace,
  context panel, filters, and asset-governance workflows.
- JSON Forms owns the structured flow-editor form rendering.
- `Zod` performs frontend validation for editor interactions.
- Backend asset contracts remain the final validation gate through FastAPI.

## Runtime Source Of Truth

The browser runtime source of truth is the Unified Catalog, not raw YAML,
Neo4j, or Qdrant. Authoring YAML remains a governed source artifact, but the
launcher reads normalized catalog APIs.

## Asset Editors

New asset-editor work should target the launcher plugin package:

```text
app/launcher/plugins/asset-editors/src/editors/
```

The flow editor is the reference implementation for the current strategy:

- JSON Schema defines editor structure.
- JSON Forms renders the visible form.
- `Zod` validates local editing state.
- FastAPI validates and versions the edited asset.

## Legacy Compatibility

There is still a legacy editor-runtime compatibility path in the repository for
generated YAML pages and older routes. That path should be treated as
compatibility infrastructure only, not as the target architecture for new
launcher work.

## Where To Read Next

- `docs/launcher/README.md`
- `docs/launcher/architecture.md`
- `docs/launcher/tech-stack.md`
- `docs/launcher/implementation-tracker.md`
