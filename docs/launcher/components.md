# Launcher Components

## shadcn Launcher Shell

Owns layout, routing, navigation, global state, panel resize behavior, and collapse behavior.

It coordinates which module is active, which flow is selected, which chat session is active, and which context panel is visible.

## Header

Contains:

- brand
- global search
- command palette
- notifications
- profile menu
- settings
- environment indicator
- quick actions
- module switcher

## Left Navigation Sidebar

Contains:

- home
- chat
- applications
- agents
- skills
- workflows
- knowledge
- MCP tools
- monitor
- reports
- admin

It should support a tree structure so top-level modules can own nested menus and submenus.

It must be collapsible and resizable.

## Center Workspace

The main work area changes depending on what the user is doing:

- launcher home
- chat workspace
- flow browser
- application module view
- workflow run view
- dynamic editor form renderer
- report dashboard
- guided flow stepper
- flow and process detail page

The chat surface should stay central to the experience. The user should be able to ask for a flow, select a suggested action, and continue into a form or workflow without losing the conversation context.

## Right Context Panel

Shows:

- selected flow
- selected process
- selected entity
- current run
- metadata
- related assets
- rulesets
- approvals
- current step
- next step
- selected module metadata
- logs and recent events
- contextual actions

It must be collapsible and resizable.

## Dynamic Form Renderer

Renders input-driven tasks derived from `user_task` metadata and plugin manifests.

It should support:

- form schemas generated from flow YAML
- user input collection
- validation hints
- required input indicators
- submit and cancel actions
- workflow start or advance calls
- binding to backend endpoints
- plugin-specific declarative screens

The form renderer is embedded inside the center workspace or a plugin route. It is not the global shell.

## Chat Workspace

The user asks questions here and the platform responds with:

- selected flow
- recommended action
- required approval
- run status
- next step
- selected module
- selected flow
- active user task

The chat is the command surface that can trigger the same kinds of actions the CLI already performs today, but through the launcher UI.

## Flow Browser

Renders the flow catalog and lets users inspect YAML-driven workflows before launching them.

It should also support browsing by module, menu, and submenu.

The flow browser should let users:

- open the flow detail view
- preview the process layout
- inspect the user task sequence
- launch an approved flow
- open the dynamic form when the flow requires user input

## Registry Loader

Knows which apps, domains, screens, workflows, forms, and permissions exist.

It should be able to return:

- module id
- module label
- icon
- submenu tree
- launch page ids
- route definitions
- renderer type
- default landing page
- permission requirements

## Event Bus

Coordinates the shell without tightly coupling panels.

Example events:

- `module.selected`
- `menu.selected`
- `flow.selected`
- `chat.intent.resolved`
- `form.opened`
- `form.submitted`
- `workflow.started`
- `workflow.updated`
- `context.changed`
- `log.event.received`

## Log Viewer

Shows:

- live events
- execution status
- trace steps
- warnings and errors
- historical runs
- approval events
- ask trace events

The log viewer can appear in the right context panel, a bottom drawer, or a dedicated run detail page.

## Launcher UI Package

The canonical launcher shell is a React + TypeScript app using shadcn/ui.

It lives in `app/launcher/`.

The previous standalone prototype in `launcher-ui/` has been removed. The launcher shell remains React/shadcn-based, and specialized form surfaces are rendered inside that shell.
