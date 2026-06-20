# Project Agent Rules

These rules apply to every development session in this repository, including
Codex, Dev1, and Dev2 handoffs.

## Mandatory Session Start

- Read `docs/launcher/implementation-tracker.md` before changing launcher,
  ingestion, AssetSet, Unified Catalog, knowledge-base projection, or workflow
  code.
- Treat the tracker as the current architecture and handoff source of truth.
- If code and tracker disagree, verify the code, then update the tracker as
  part of the same work.

## Mandatory Tracker Updates

Always update `docs/launcher/implementation-tracker.md` before finishing a
session when the work changes any of these areas:

- Asset versioning or AssetSet lifecycle.
- Ingestion paths, staging, loaders, or generated asset formats.
- Launcher runtime behavior, JSON Forms asset editors, editor UX, or module
  routing.
- FastAPI endpoints used by the launcher or catalog.
- Unified Catalog schema, active version selection, deployment, rollback, or
  projection behavior.
- Verification commands, smoke-test results, known blockers, or pending tasks.

The tracker update must record:

- What changed.
- Why it changed if architecture or ownership moved.
- New or changed source paths.
- Affected endpoints or commands.
- Current status, verification performed, and remaining TODO/BLOCKED items.

## Asset Architecture Reminder

- Governed AssetSet YAML source lives under
  `app/assets/catalog/modules/<module>/assetsets/<set>/`.
- `app/launcher/modules` is not the default governed AssetSet source for
  runtime loading.
- Runtime reads active versions from the Unified Catalog through FastAPI.
- Editing creates immutable AssetSet versions; changes do not affect runtime
  until review, validation, and deployment activate the new version.

## Launcher Editor Architecture

All asset editors in the launcher MUST follow the plugin pattern:

### Required Stack

- JSON Forms (`@jsonforms/react` + `@jsonforms/vanilla-renderers`) for form rendering
- Zod (`zod@^3.25.76`) for client-side validation
- React 19 + TypeScript (Vite 8)
- Inline styles with shared `colors` palette

### Plugin Location

```
app/launcher/plugins/asset-editors/src/editors/<name>-editor/
├── index.js                    # Public exports
├── components.js               # React components (h() pattern)
├── helpers.js                  # Zod schemas + normalizers + validators
├── <name>.schema.json          # JSON Schema
├── <name>.ui-schema.json       # UI Schema for JSON Forms
└── validators.test.js          # Unit tests
```

### Editor Contract

Each editor receives `{ value, onChange, readOnly }` where `value` is the
full asset document. Editors must provide tabs: Structured Editor, Raw Source,
Relations, History.

### Existing Editors

- `flow-editor` - Flow definitions with user tasks, actions, tools
- `ontology-editor` - Entity definitions with aliases and relations (planned)
- `business-rule-editor` - Business rules with conditions and gates (planned)
- `navigation-editor` - Domain/module/menu hierarchy (planned)

### DO NOT

- Do NOT create new inline editors in `AssetInlineEditor.tsx`
- Do NOT use `GenericPayloadView` for new asset types
- Do NOT duplicate shared utilities (colors, buttonStyle, inputStyle, etc.)
