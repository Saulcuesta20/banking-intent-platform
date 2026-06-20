# Enterprise AI Launcher Components And Tech Stack

> This document now summarizes the active launcher component model. Older
> Lowdefy-shell planning notes were removed because they no longer describe the
> implementation direction.

## Active Component Model

### 1. React Launcher Shell

Owns:

- top navigation
- left navigation
- central workspace
- right governance/detail panel
- domain and module navigation
- launcher state and routing

### 2. Asset Editor Plugin Layer

Lives in:

```text
app/launcher/plugins/asset-editors/
```

Owns:

- asset-specific editor packages
- editor composition helpers
- modal and editor state for structured editing
- schema-driven rendering for supported assets

### 3. Flow Editor Surface

The flow editor is the current reference editor.

Owns:

- JSON Schema contracts for visible fields
- JSON Forms rendering
- task/action/tool editing UI
- `Zod` validation before save

### 4. FastAPI Catalog Boundary

Owns:

- asset lookup
- validation
- preview
- version creation
- review transitions
- deployment and rollback

### 5. Unified Catalog

Owns:

- canonical asset versions
- AssetSet lifecycle
- deployment state
- relationship graph for governed assets

## Current Tech Stack

### Frontend

- React
- TypeScript
- Vite
- shadcn/ui
- TanStack Query
- JSON Forms
- Zod

### Backend

- Python
- FastAPI
- LangGraph
- SQLite catalog
- Neo4j graph projection
- Qdrant vector projection

## Active UI Contract

The active asset-editor contract is:

```text
JSON Schema
-> JSON Forms
-> local Zod validation
-> FastAPI contract validation
-> Unified Catalog versioning
```

## Legacy Note

Generated YAML pages and legacy editor-runtime routes may still exist for
compatibility, but they are not the target path for new asset editors.

## Canonical References

- `docs/launcher/architecture.md`
- `docs/launcher/tech-stack.md`
- `docs/launcher/implementation-tracker.md`
