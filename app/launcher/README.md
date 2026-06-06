# Enterprise AI Launcher Shell

React + TypeScript launcher shell built with shadcn/ui patterns.

Lowdefy is embedded as the dynamic runtime for catalog screens, asset editors,
and future flow forms.

## Run

```bash
npm run dev
```

This starts:

- shell: `http://localhost:3000`
- Lowdefy runtime: `http://localhost:3002`
- module watcher: watches `modules/**/*.json`

## AssetSets And Unified Catalog

Launcher assets are authored as versioned AssetSet YAML folders and deployed to
the Unified Catalog:

```bash
cd /home/saul/banking-intent-platform
.venv/bin/python -m app.launcher_cli assets export
.venv/bin/python -m app.launcher_cli assets load
```

New versions enter `ready_for_review`. Review and deployment are performed in
the launcher `Assets` workspace. The launcher reads active versions from the
Unified Catalog; YAML and Neo4j are not launcher runtime registries.

## Backend

By default the shell calls:

```text
http://127.0.0.1:8030
```

Override it with:

```bash
VITE_LAUNCHER_API_URL=http://127.0.0.1:8030 npm run dev
```

Chat questions are sent to `app/ask` through the backend `/ask` endpoint. The launcher does not perform local intent routing.

The relevant endpoints are:

- `POST /ask`
- `GET /launcher/home`
- `GET /launcher/flows/{flow_id}`
- `GET /catalog/assets`
- `POST /catalog/assets/validate`
- `POST /catalog/assets/{id}/versions`
- `GET /catalog/asset-sets`
- `POST /catalog/asset-sets/{id}/transition`
- `POST /catalog/asset-sets/{id}/deploy`
- `POST /catalog/asset-sets/{id}/rollback`
- `POST /orchestrator/process/execute`
- `GET /orchestrator/executions`

## Lowdefy Runtime

Module configuration lives in:

```text
modules/<domain>/<module>/module.json
modules/<domain>/<module>/processes/<process>/process.json
modules/<domain>/<module>/forms/<form>/versions/<version>/form.json
```

Current domains:

- `master-data`
- `deposits`
- `lending`

Lowdefy pages are generated from versioned module forms into:

```text
lowdefy-runtime/lowdefy.yaml
```

This YAML is a generated renderer artifact, not the runtime business source of
truth. The `asset-explorer` Lowdefy page renders the Asset Studio and queries
the Unified Catalog APIs.

### Lowdefy Asset Editors

The local plugin is located at:

```text
lowdefy-plugins/asset-editors/
```

| Block | Purpose |
|---|---|
| `AssetCodeEditor` | YAML/JSON source editor with syntax validation |
| `ProcessCanvas` | Flow and process node editor |
| `OntologyGraph` | Entity, concept, ontology, and relationship editor |
| `RuleBuilder` | Business rule condition and outcome editor |
| `FormDesigner` | Form field editor with live preview |
| `NavigationTree` | Domain, module, menu, and submenu editor |
| `AssetStudio` | Catalog browser and editor router |

The editor validates through FastAPI. Saving creates a new immutable AssetSet
patch version under `modules/<module>/assetsets/<set>/versions/<version>/` and
submits it as `ready_for_review`. Review, validation, and deployment are then
performed from the same Lowdefy workspace. Existing versions are never
overwritten.

Generate Lowdefy config with:

```bash
npm run generate:lowdefy
```

This writes both:

```text
lowdefy-runtime/lowdefy.yaml
public/module-registry.json
```

See:

```text
docs/module-runtime.md
```

Override the runtime URL with:

```bash
VITE_LOWDEFY_RUNTIME_URL=http://localhost:3002 npm run dev:shell
```

## Architecture Boundary

- shadcn/React owns the shell, navigation, chat workspace, context panel, resizing, and collapse behavior.
- Lowdefy owns the Asset Studio editors and remains the dynamic runtime target for YAML-driven flow forms and declarative module screens.
- FastAPI owns catalog queries, lifecycle validation, deployment, Ask resolution, workflow execution, and trace.
- Unified Catalog owns canonical versions, review history, AssetSet deployments, and the active launcher view.
- Neo4j, Qdrant, and Document KB are governed projections used by Ask and retrieval.
- The right panel renders Ask and workflow traces as numbered steps with a concise result for each step.
