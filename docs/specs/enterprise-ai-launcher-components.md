# Enterprise AI Launcher Components And Tech Stack

## Purpose
This document breaks down the components needed to build the Enterprise AI Launcher and explains where Lowdefy fits in the architecture.

The goal is to keep the launcher as a separate deployable app inside the same monorepo, while reusing the current platform services for ingestion, ask, workflow execution, knowledge retrieval, audit, and approval.

## Feasibility Of Lowdefy

Lowdefy is a good fit for the launcher because it is a config-first app stack built around YAML app definitions, blocks, actions, requests, and plugins. Its documentation shows that pages are assembled from blocks, blocks can trigger events and actions, and external services can be integrated through requests and connections. That matches the launcher need very well: the launcher must render flow catalogs, forms, log panels, master-detail views, and operational dashboards from structured metadata.

What Lowdefy is especially good at:

- rendering YAML-defined pages and workflows
- building internal tools, dashboards, forms, and admin-style shells
- wiring UI actions to requests against backend APIs
- extending behavior with custom blocks and plugins

What Lowdefy should not do:

- own the workflow engine
- own ingestion or KB persistence
- replace the ask/runtime services
- execute business tools directly

Short version: Lowdefy is feasible and well suited as the launcher presentation layer, but it should stay a UI shell over the platform services.

## Component Breakdown

### 1. Launcher Shell
The top-level application shell that owns navigation, routing, global search, profile controls, notifications, and the overall page layout.

Responsibilities:

- render the top header
- render left navigation
- route between launcher home, chat, flows, logs, and admin surfaces
- expose the right context panel
- keep application state such as the selected domain, selected flow, and selected run

### 2. Lowdefy Page Renderer
The config-driven UI layer that renders launcher pages and panels.

Responsibilities:

- transform flow and process metadata into Lowdefy pages
- render cards, tables, tabs, forms, steppers, and collapsible panels
- execute UI actions such as open page, fetch data, set state, and submit form
- support custom blocks for views that need a richer canvas

### 3. Flow Catalog Service
The backend service that exposes approved flow and process definitions to the launcher.

Responsibilities:

- list published flows
- return flow detail payloads
- return process detail payloads
- provide `user_task`, `user_action`, `ruleset`, `asset_set`, and trace metadata
- keep flow definitions as the source of truth

### 4. Workflow Run Service
The runtime service that starts and tracks workflow executions.

Responsibilities:

- start a flow from the launcher
- create a workflow run id
- stream run status and events
- expose run history
- persist trace information for inspection

### 5. Chat Workspace
The conversational center of the launcher.

Responsibilities:

- accept natural-language requests
- propose actions or workflows
- ask for confirmation when needed
- show structured results
- coordinate with the flow launcher and context panel

### 6. Context And Detail Panel
The right-side information surface.

Responsibilities:

- show selected entity, flow, process, or run
- show metadata, ownership, rulesets, and linked assets
- show related documents and execution history
- expose quick actions and drill-downs

### 7. Log And Trace Viewer
The operational observability surface.

Responsibilities:

- show live logs for the active run
- show trace events for ask, workflow execution, and approvals
- show errors and warnings
- support filtering by run, flow, time, and severity

### 8. Search And Discovery
Global search for apps, flows, entities, rules, and runs.

Responsibilities:

- search by human text
- search by canonical asset id
- search by aliases
- navigate directly to a flow or entity detail page

### 9. Notification Center
The alert and events surface.

Responsibilities:

- show workflow approvals
- show execution failures
- show ingestion updates
- show user and system notifications

### 10. Domain Registry
The launcher registry that knows what modules and domains exist.

Responsibilities:

- list available applications and domains
- drive the launcher cards
- provide domain metadata for the sidebar
- map UI entry points to backend endpoints

### 11. Auth And Session Layer
Shared authentication and authorization.

Responsibilities:

- authenticate users
- enforce role-based access to domains and actions
- propagate session context to backend calls
- support environment-aware access rules

### 12. Audit And Telemetry
Operational records of what the launcher did.

Responsibilities:

- record launches
- record approvals
- record workflow starts and completions
- record failed requests and user actions

## How Flow YAML Becomes UI

The launcher should not read raw YAML directly in the browser as the only source of truth. Instead, the backend should normalize the YAML into a launcher-ready page model.

Suggested path:

```text
flow/process YAML
-> flow catalog service
-> launcher page model
-> Lowdefy page config
-> rendered launcher screen
```

The mapping can look like this:

- `flow` -> flow browser card, detail page, launch action
- `process` -> process summary, step table, run preview
- `user_task` -> form or task panel
- `user_action` -> buttons, actions, or tool invocations
- `ruleset` -> validation and guardrail display
- `asset_set` -> grouped detail page or transaction workspace

## Tech Stack

### Frontend And Launcher Layer

- Lowdefy for YAML-driven launcher pages
- Custom Lowdefy blocks/plugins for logs, traces, and specialized flow visualization
- React-based custom blocks when the stock Lowdefy blocks are not enough
- CSS/Ant Design-like layout conventions provided by Lowdefy defaults

### Backend Platform

- Python services for ingestion, ask, catalog, and workflow execution
- LangGraph for orchestration
- Neo4j for graph-backed knowledge
- Qdrant for alias and semantic memory
- SQLite for catalog and lightweight knowledge stores
- FastAPI for HTTP integration points

### Integration Surface

- REST APIs for flow catalog, run status, search, and logs
- Request/response actions from Lowdefy to backend services
- Optional streaming channel for live logs if needed later

### Data And Authoring

- YAML flow and process definitions
- YAML-based launcher pages
- structured trace JSON
- asset catalog records
- alias and relation memory

## Suggested Repository Boundaries

Recommended layout:

- `app/launcher` for the React + TypeScript shadcn launcher shell
- `app/` for the current platform backend
- `config/definitions` for flow and process YAML
- `docs/specs` for product and architecture specs

If the team wants stronger isolation later, the launcher can be moved to a separate repository without changing the backend APIs, as long as the page-data contract remains stable.

## MVP Development Order

1. Flow catalog API
2. Lowdefy launcher shell
3. Flow browser and flow detail pages
4. Chat workspace
5. Log and trace viewer
6. Context panel
7. Workflow run start/stop screens
8. Admin and settings surfaces
9. Custom blocks for advanced flow rendering

## Bottom Line

Yes, it is feasible to integrate Lowdefy with the flow-oriented launcher we are designing.

The important boundary is this:

- Lowdefy renders the launcher and workflow views.
- The backend services own the actual workflow logic, ingestion, ask, approval, audit, and knowledge persistence.

That separation makes the integration practical, maintainable, and safe.

## References

- Lowdefy documentation: https://docs.lowdefy.com/
- Lowdefy blocks and page composition: https://docs.lowdefy.com/blocks
- Lowdefy events and actions: https://docs.lowdefy.com/events-and-actions
- Lowdefy connections and requests: https://docs.lowdefy.com/connections-and-requests
- Lowdefy plugins: https://docs.lowdefy.com/plugins-introduction
- Lowdefy GitHub: https://github.com/lowdefy/lowdefy
