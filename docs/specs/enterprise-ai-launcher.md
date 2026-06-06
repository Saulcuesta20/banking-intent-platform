# Enterprise AI Launcher

> Canonical launcher documentation now lives under `docs/launcher/`.
> Start with [docs/launcher/README.md](../launcher/README.md).

## 1. Recommendation

My recommendation is to build the launcher as a **separate deployable app** inside the same monorepo, not as a loose set of components inside the current product.

That gives us:

- a clean UI boundary
- independent release cadence
- the ability to evolve the launcher shell without risking the ingestion/knowledge platform
- shared domain models, APIs, and auth with the current platform

So the structure I would use is:

- one product shell for the launcher
- one shared backend/domain layer for ingestion, ask, workflow, knowledge, and plugins
- one shared design system

For the UI shell, Lowdefy is the primary fit because it is a YAML/JSON-driven app framework for business apps, built on top of Next.js and Auth.js, with blocks, actions, requests and plugins that fit internal tools, dashboards, forms, and workflow apps. That makes it a good match for a launcher that needs to render flows, master-detail panels, chat, logs, and action panels from structured definitions rather than hand-coded screens.

The launcher shell now lives in `app/launcher/` as a React + TypeScript application using shadcn/ui patterns. Lowdefy remains useful as a dynamic runtime for YAML-driven forms and plugin screens, but it is not the canonical shell package.

If we keep everything in a single app, the launcher will eventually swallow the platform. This should stay a Lowdefy shell, not become the whole house.

## 2. Product Shape

The launcher should be the place where a user can:

- search
- ask questions in chat
- inspect context
- launch workflows
- open forms
- see live logs
- receive notifications
- navigate domains and applications

The launcher should not be just a homepage. It should be the operational front door to the platform.

## 3. Core Layout

The layout reflected in the prototypes is the right direction:

- top header
- left navigation rail
- central chat / workspace
- right context panel
- optional bottom status bar

That structure works well for:

- fast navigation
- conversational execution
- contextual inspection
- auditability

## 4. Recommended Panels

### Header

Contains:

- global search
- notifications
- user menu
- environment indicator
- settings

### Left Rail

Contains:

- home
- chat
- agents
- skills
- workflows
- knowledge
- tools
- monitor
- admin

### Main Workspace

This should be context-driven and switch between:

- launcher home
- chat workspace
- app explorer
- workflow designer
- form renderer
- report dashboard
- log console

### Right Context Panel

This should show:

- selected entity
- metadata
- history
- logs
- actions
- related documents
- related assets

### Lowdefy Fit

Lowdefy is a good candidate for the launcher presentation layer because:

- launcher screens can be described as YAML pages and blocks
- chat-driven events can trigger Lowdefy actions
- forms can be rendered from flow and user-task metadata
- dashboards, lists, tabs, drawers, and context panels are already a natural match for Lowdefy blocks
- custom plugins can bridge the launcher shell with the current backend APIs

Lowdefy should not own the workflow engine, ingestion logic, or KB persistence. It should own the visual shell and route user intent to the platform services.

### Flow Rendering Strategy

The launcher should render flow and process definitions through a dedicated UI mapping layer:

- source input: `config/definitions/flows/*.flow.yaml`
- source input: `config/definitions/processes/*.process.yaml`
- derived input: `user_task`, `user_actions`, required inputs, rulesets, and asset sets
- launcher output: Lowdefy page schema, cards, steppers, forms, tables, logs, and master-detail views

This keeps the YAML flow definitions as the product source of truth, while Lowdefy remains the presentation engine. If we need richer diagramming later, we can add a custom Lowdefy plugin or a companion canvas block without changing the flow model.

## 5. Chat Behavior

The chat should be the execution brain of the launcher, but not the place where everything is rendered.

The chat should:

- answer questions
- infer intent
- propose actions
- launch workflows
- create records
- request confirmation when needed
- emit structured events

The chat should not become a second UI tree. It should be an event generator.

## 6. Logs And Trace

The launcher needs a first-class log experience.

I would expose logs in three ways:

- a right-side collapsible log panel
- a dedicated trace view for each action or workflow
- a history panel for past runs, errors, approvals, and agent activity

This matters because the user wants to understand what is happening while the system is operating.

## 7. Component Architecture

At a logical level, I would split the launcher into these modules:

- `launcher-shell`
- `global-search`
- `chat-workspace`
- `context-panel`
- `workflow-launcher`
- `form-renderer`
- `log-viewer`
- `notification-center`
- `app-registry`
- `entity-explorer`
- `command-router`
- `lowdefy-shell`

The shell should orchestrate these modules, not own business logic directly.

## 8. Runtime Flow

The main runtime flow should look like this:

```text
user input
-> intent understanding
-> route to domain/app
-> chat proposes action or workflow
-> user confirms if needed
-> workflow executes
-> logs and context update
-> result shown in workspace and detail panel
```

## 9. Where The Launcher Fits

The launcher should sit above:

- ingestion
- ask
- workflow execution
- knowledge graph
- plugins and tools

It should not replace those systems.

It should unify access to them.

## 10. My Opinion On Project Boundary

My recommendation is:

1. keep the launcher in the same monorepo
2. turn it into a separate Lowdefy UI package
3. share backend APIs, models, and auth
4. keep ingestion and ask as independent services

That is the best balance between speed and discipline.

If we put it fully inside the current app, the UI will start to leak into the domain engine.
If we split it into a totally separate repository, we will pay too much coordination cost too early.

The middle path is the one I would pick.

## 11. MVP Scope

The first version of the launcher should include:

- search
- chat
- launcher cards
- entity master/detail
- workflow execution entry points
- Lowdefy-rendered flow browser
- Lowdefy-rendered flow and process forms
- logs
- notifications
- settings
- live log inspector
- YAML-driven workflow preview

The first version should not include:

- full admin studio
- full workflow designer
- deep plugin marketplace
- advanced analytics hub

Those can come later.

## 12. Decision Summary

- Keep the launcher as a separate app inside the monorepo.
- Share domain models and APIs.
- Make chat the command center.
- Make logs visible and actionable.
- Keep the layout anchored around header, navigation, center workspace, and context panel.
- Use this launcher as the front door for ask + workflow + ingestion visibility.
- Use Lowdefy for the launcher shell and workflow forms/panels, while keeping domain logic in the platform services.

For the full component and tech stack breakdown, see
`docs/specs/enterprise-ai-launcher-components.md`.
