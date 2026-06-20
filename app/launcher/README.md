# Enterprise AI Launcher Shell

React + TypeScript launcher shell built with shadcn/ui patterns.

The launcher now runs as a single front-end application on port `3000`. Asset
editing is launcher-native and uses:

```text
JSON Schema -> JSON Forms -> Zod -> FastAPI contract validation
```

There is no longer a separate Lowdefy editor runtime or a second UI port.

## Run

```bash
npm run dev
```

This starts:

- shell: `http://localhost:3000`
- module watcher: watches `modules/**/*.json`

## Build

```bash
npm run build
```

Before build, the launcher regenerates:

```text
public/module-registry.json
```

from the module manifests under:

```text
modules/<domain>/<module>/
```

## AssetSets And Unified Catalog

Launcher assets are governed as AssetSets and deployed to the Unified Catalog:

```bash
cd /home/saul/banking-intent-platform
.venv/bin/python -m app.launcher_cli assets export
.venv/bin/python -m app.launcher_cli assets load
```

New versions enter `ready_for_review`. Review and deployment are performed in
the launcher `Assets` workspace. The launcher reads active versions from the
Unified Catalog; YAML, Neo4j, and Qdrant are not browser runtime registries.

## Backend

By default the shell calls:

```text
http://127.0.0.1:8030
```

Override it with:

```bash
VITE_LAUNCHER_API_URL=http://127.0.0.1:8030 npm run dev
```

Relevant endpoints:

- `POST /ask`
- `GET /launcher/home`
- `GET /launcher/flows/{flow_id}`
- `GET /catalog/metadata`
- `GET /catalog/assets`
- `GET /catalog/assets/{id}`
- `POST /catalog/assets/validate`
- `POST /catalog/assets/{id}/preview`
- `POST /catalog/assets/{id}/versions`
- `GET /catalog/asset-sets`
- `POST /catalog/asset-sets/{id}/transition`
- `POST /catalog/asset-sets/{id}/deploy`
- `POST /catalog/asset-sets/{id}/rollback`
- `POST /orchestrator/process/execute`
- `GET /orchestrator/executions`

## Active Editor Surface

The structured flow editor lives under:

```text
plugins/asset-editors/src/editors/flow-editor/
```

The launcher opens editors from the Unified Catalog view instead of jumping to
an external renderer. FastAPI remains the authority for validation, preview,
versioning, review, and deployment.

## Architecture Boundary

- React/shadcn owns the shell, navigation, workspace, context panel, and state.
- JSON Forms owns the structured flow editor form rendering.
- Zod owns frontend validation for editing interactions.
- FastAPI owns catalog queries, validation, version creation, lifecycle, Ask,
  orchestration, and trace.
- Unified Catalog owns canonical asset versions and active runtime visibility.
- Graph, vector, document, and relational stores are backend projections, not
  independent launcher sources of truth.
