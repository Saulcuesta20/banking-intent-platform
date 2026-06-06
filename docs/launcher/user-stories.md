# Launcher User Stories

## Story 1: Browse Flows
As an operations analyst, I want to browse approved flows so that I can inspect the available workflows without opening raw YAML.

Acceptance criteria:

- Flow cards are rendered from catalog data.
- A selected flow opens a detail view.
- The detail view includes tasks, actions, rulesets, and context.
- The browser supports module-based navigation, not just a flat list.

## Story 1b: Navigate Application Modules
As an operations analyst, I want to browse application modules and submenus so that I can find the right domain area quickly.

Acceptance criteria:

- The launcher exposes an application registry.
- Modules such as Loan, Savings Account, and Credit Card can be added without redesigning the shell.
- Each module can have its own menus, submenus, and launcher cards.
- The module tree can grow without breaking the current launcher layout.

## Story 2: Launch A Workflow
As an operations analyst, I want to start a workflow from the launcher so that I can move from intent to execution in one place.

Acceptance criteria:

- The launcher shows a launch action for approved flows.
- Starting a flow creates a run id.
- The launcher shows run status and execution trace.
- The launcher shows the selected module and flow context while the run is active.

## Story 3: Chat With Context
As a user, I want to ask the launcher a question so that it can propose the right flow or action.

Acceptance criteria:

- Chat can resolve to a known flow.
- The launcher shows the selected context.
- The response includes approval requirements when applicable.
- The chat can trigger the same workflow-oriented behavior that is available from CLI today.
- The chat can open the relevant module and prepare the center panel for the next `user_task`.

## Story 4: Inspect Logs
As a platform engineer, I want to see logs while a flow runs so that I can understand the system behavior.

Acceptance criteria:

- Live logs are visible in the right panel or a dedicated view.
- Failed steps are highlighted.
- Historical trace data can be reopened later.
- Log events can be filtered by module, flow, and run.

## Story 5: Render User Tasks
As an operations analyst, I want user tasks rendered as forms and actions so that I can complete the work without reading the underlying YAML.

Acceptance criteria:

- `user_task` metadata drives the form layout.
- `user_action` entries become buttons or tool invocations.
- Required inputs are validated before submission.
- The center panel renders the active `user_task` sequence step by step.
- The current step is visible in the center panel, not hidden in a side panel.

## Story 6: Follow A Guided Flow
As a user, I want the launcher to show the active user task sequence in the center panel so that the workflow feels like a guided conversation and not a static page.

Acceptance criteria:

- The center panel shows the current step in the `user_task` sequence.
- The sequence can present front action, user input, and back action/tool invocation.
- The panel updates as the workflow advances.
- The sequence can be launched from chat or from the module launcher cards.

## Story 7: Add A New Business Module
As a platform owner, I want to add a new business module without redesigning the launcher so that the shell can grow with the product.

Acceptance criteria:

- A new module can be registered with menu and submenu entries.
- The launcher can show a new module card on the home screen.
- The module can expose its own flow pages and detail views.

## Story 8: See Active Step And Next Step
As an operations analyst, I want to see the current step and the next step so that I can understand where the workflow is going.

Acceptance criteria:

- The launcher highlights the active step.
- The launcher shows a next-step hint when available.
- The run view updates when the step advances.
