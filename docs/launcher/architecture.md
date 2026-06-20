# Launcher Architecture

## Purpose

Describe the current launcher architecture after the migration to a single
React runtime and launcher-native asset editors.

## Architecture Overview

The launcher is a React + TypeScript + shadcn/ui application inside the
monorepo. It owns:

1. left navigation sidebar
2. center workspace
3. right governance/detail panel

The center workspace can host chat, catalog exploration, and asset editing
without leaving the launcher shell.

## Runtime Source Of Truth

The runtime source of truth is the Unified Catalog exposed by FastAPI.

The browser does not read:

- raw YAML
- Neo4j
- Qdrant
- staging files

directly at runtime.

## Asset Editing Model

The active editor model is:

```text
JSON Schema
-> JSON Forms
-> Zod
-> FastAPI asset validation
-> Unified Catalog draft version
```

The flow editor is the current reference implementation.

## Asset Governance Workspace

The launcher `Assets` workspace provides:

- catalog tree view
- route view
- asset detail
- inline editing
- review actions
- deployment actions
- AssetSet history

The tree renders Catalog as the single governed root. Backend projections may
exist operationally, but they are not shown as independent authorities in the
launcher browser.

## Layer Boundaries

### Frontend

- React/shadcn: layout, navigation, state, browsing, shell interactions
- JSON Forms: structured editor rendering
- Zod: editor interaction validation

### Backend

- FastAPI: launcher APIs
- Unified Catalog: canonical asset store
- projection services: graph, vector, document, relational updates during
  deployment

## Deployment Model

```text
author/edit asset
-> create draft AssetSet version
-> ready_for_review
-> in_review
-> validated
-> deploy
-> active in Unified Catalog
-> rebuild backend projections
```

## Guiding Rule

Do not let the launcher create a second source of truth. The UI edits and
displays governed catalog data, but lifecycle, validation, deployment, and
projection decisions remain backend responsibilities.
