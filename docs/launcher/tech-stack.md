# Launcher Tech Stack

## Frontend Decision

The launcher shell should be built with **React + TypeScript + shadcn/ui**, using shadcn-admin as a layout and interaction reference.

Lowdefy remains part of the platform, but it should not own the global launcher shell. Its role is the dynamic runtime for forms, declarative screens, and plugin-specific UI where YAML-driven rendering is useful.

This changes the previous decision:

- **shadcn/ui owns the shell**: top navigation, left navigation, center chat/workspace, right context panel, routing, resize behavior, collapse behavior, command palette, tables, drawers, and page-level composition.
- **Lowdefy owns dynamic rendering**: flow forms, generated task screens, plugin screens, declarative internal pages, and binding for YAML-defined workflow inputs.
- **FastAPI owns execution**: flow discovery, intent resolution, workflow runs, approvals, audit, logs, and knowledge retrieval.

## TypeScript

Use **TypeScript** for the launcher frontend.

Reason:

- shadcn/ui and shadcn-admin patterns are strongest in the React/TypeScript ecosystem.
- The launcher needs typed contracts for plugin manifests, dynamic menus, route definitions, flow schemas, chat events, context-panel payloads, and API clients.
- The frontend event bus needs explicit event names and payload shapes.
- Lowdefy schemas and YAML plugin manifests can be validated into TypeScript types on the UI side and Pydantic models on the backend side.

The backend remains Python. TypeScript is for the frontend shell and frontend integration contracts.

## Primary Frontend Stack

- React
- TypeScript
- Vite or Next.js, to be selected during implementation
- shadcn/ui
- shadcn-admin patterns for admin layout, density, navigation, and app structure
- Tailwind CSS
- React Router or Next.js routing
- TanStack Query for API state
- Zustand or a small typed store for shell state
- React Hook Form or TanStack Form for custom coded forms
- embedded Lowdefy runtime for declarative forms and plugin screens

## shadcn/ui Components To Use

- `Sidebar` for the left application navigation
- `Resizable` for left, center, and right panel sizing
- `Collapsible` for menus, submenus, and context sections
- `Command` for global search and command palette
- `Sheet` and `Dialog` for secondary workflows
- `Tabs` for chat, flow, logs, and detail views
- `Table` for runs, activity, entities, and logs
- `Card` only for repeated launcher tiles or contained content, not for page sections
- `Form`, `Field`, `Input`, `Select`, `Textarea`, and validation components for coded forms

## Lowdefy Role

Lowdefy should be used as a **dynamic form and declarative plugin engine**.

Good Lowdefy use cases:

- render forms generated from existing flow YAML
- render `user_task` input screens
- bind form submissions to workflow endpoints
- host plugin-specific declarative pages
- render simple dashboards or operational views supplied by plugin manifests
- keep business-specific UI configurable when code changes are not warranted

Lowdefy should not own:

- the three-panel launcher layout
- global routing
- the persistent chat shell
- the collapsible/resizable sidebars
- the global command palette
- cross-module navigation
- the right context panel framework
- the plugin registry itself

## Backend

- Python
- FastAPI
- LangGraph
- OpenAI-compatible LLM providers
- Neo4j
- Qdrant
- SQLite
- current ingestion, ask, audit, approval, and workflow services

## Integration

- REST APIs from the TypeScript launcher to FastAPI
- typed frontend API client generated or maintained from backend contracts
- registry endpoints for apps, menus, screens, workflows, permissions, and plugin metadata
- flow catalog endpoints for YAML flows and process definitions
- run lifecycle endpoints for starting and tracking workflows
- chat endpoints for intent resolution and flow selection
- trace/log endpoints for live and historical events
- Lowdefy runtime adapter for dynamic forms and plugin pages

## Data And Manifests

- flow YAML
- process YAML
- plugin manifests
- menu manifests
- screen manifests
- workflow manifests
- permission manifests
- launcher registry records
- trace JSON
- asset catalog records
- alias and relation memory
- audit records

Recommended plugin structure:

```text
plugins/
  loan/
    plugin.yaml
    menu.yaml
    screens.yaml
    workflows.yaml
    forms.yaml
    permissions.yaml
```

## Why This Stack Works

shadcn/ui gives us direct control over the launcher experience, which is necessary for the three-panel layout, collapsible panels, resizing, chat-centered workflow, and right-side context panel.

Lowdefy still fits the system, but in the place where it is strongest: dynamic forms and declarative plugin screens backed by YAML and backend contracts.

This split avoids forcing Lowdefy to behave like a full custom application shell while preserving its value for flows, forms, and plugin-driven screens.
