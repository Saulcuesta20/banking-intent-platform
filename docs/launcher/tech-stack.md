# Launcher Tech Stack

## Frontend Decision

The launcher shell is built with:

- React
- TypeScript
- Vite
- shadcn/ui patterns

## Asset Editor Stack

The current asset-editor strategy is:

- JSON Schema as editor contract
- JSON Forms as structured renderer
- Zod as local editor validator
- FastAPI + backend asset contracts as final validation

## Backend

- Python
- FastAPI
- LangGraph
- SQLite Unified Catalog
- Neo4j graph projection
- Qdrant vector projection

## Why This Stack

React/shadcn gives the launcher direct control over:

- three-panel layout
- navigation
- state
- responsive admin workflows
- modal and drawer interactions

JSON Forms keeps the editors aligned with the governed asset contracts without
forcing the UI to hand-code every field layout from scratch.

Zod catches editing issues early in the browser, while FastAPI remains the
authoritative gate before a new catalog version is created.

## Integration Surface

- REST APIs from launcher to FastAPI
- generated module registry from local module manifests
- Unified Catalog endpoints for assets, AssetSets, review, and deployment
- Ask and orchestration endpoints for runtime flows

## Non-Goals

The launcher should not:

- read YAML directly at runtime
- read Neo4j or Qdrant directly at runtime
- own lifecycle rules
- own deployment logic
- own projection logic

Those responsibilities stay in backend services.
