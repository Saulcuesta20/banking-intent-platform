# Launcher Vision

## Product Goal
Build an enterprise launcher that acts as the user's operational front door to the platform.

The launcher should not be a landing page. It should be the place where users can search, chat, inspect context, launch workflows, and understand what the system is doing while it runs.

## Core Vision

We want a launcher that can:

- render approved flows from YAML
- show workflow state and traceability
- expose logs, metadata, and context in one screen
- use chat as the command layer
- grow with new application modules, menus, and submenus such as Loan, Savings Account, Credit Card, and future business domains
- keep execution behind backend services and approval gates

The launcher should feel like an enterprise operating console, not a decorative portal. It needs to support a dense working style where the user can move from discovery to execution without leaving the shell.

## Core Feature Set

The launcher should include these capabilities:

- application registry for modules and submodules
- launcher cards for domain entry points
- flow browser driven by YAML definitions
- process browser driven by YAML definitions
- chat workspace for natural-language requests
- center panel that paints the active `user_task` sequence
- live log and trace viewer
- right context panel for metadata and related assets
- approval and confirmation checkpoints
- global search across modules, flows, entities, rules, and runs
- notifications and event center
- admin and settings areas
- workflow launch and run tracking
- low-code / config-driven form and plugin rendering through Lowdefy
- support for coded shadcn screens when a specialized canvas is needed

## What The Launcher Must Show

The user should be able to see, at minimum:

- the selected module
- the selected flow or process
- the current `user_task`
- the active `user_action`
- the context entity or transaction
- the related ruleset
- the current run status
- the live logs and trace events
- the required approval state
- the next step in the sequence

## Module Vision

The shell must support a growing set of enterprise business modules. Examples:

- Loan
- Savings Account
- Credit Card
- Transfers
- Customer Service
- Risk
- Compliance
- Operations
- Admin

Each module can contribute its own:

- menu entries
- submenu entries
- launcher cards
- detail pages
- forms
- flow definitions

This makes the launcher a container for many business capabilities rather than a single purpose screen.

## Why It Exists

The platform already knows how to ingest, resolve, approve, and trace business knowledge. The launcher exists to turn that capability into a single, coherent workspace.

## UX Principles

- One screen, many contexts
- Chat is the command center
- Logs are first-class
- Flow and process definitions stay human-readable
- The UI should explain the system, not hide it
- The center panel should evolve step by step as the `user_task` sequence advances
- The launcher should support both browsing and execution
- Module navigation should feel expandable, not fixed
- Operators should be able to move from chat to workflow and back without losing context

## Hybrid UI Fit

The launcher should use a hybrid UI model:

- shadcn/ui owns the shell and primary application experience
- Lowdefy owns dynamic forms, YAML-driven flow screens, and plugin-specific declarative pages
- FastAPI owns workflow execution, registry data, approvals, logs, and knowledge access

This split is necessary because the launcher needs a highly controlled three-panel experience with collapsible and resizable sidebars, persistent chat, and a right context panel. That behavior is better handled by a custom React + TypeScript shell.

Lowdefy can render:

- forms derived from user tasks
- declarative plugin pages
- simple module-specific pages
- YAML-driven operational views
- workflow input screens
- form bindings to backend endpoints

Lowdefy should not own:

- the launcher shell
- global navigation
- the persistent chat workspace
- the right context panel framework
- sidebar resize and collapse behavior
- workflow logic
- ingestion
- the knowledge base

Python can help generate or validate Lowdefy schemas, but the visual shell belongs to the React + TypeScript launcher.

## Operational Experience

The launcher should support the same working pattern that we already use from the command line, but in a visual shell:

1. the user asks a question or selects a module
2. the launcher resolves the relevant flow or process
3. the center panel paints the user task sequence
4. the right panel shows metadata, rules, and context
5. the log panel shows what is happening as it happens
6. the user confirms or continues
7. the workflow completes and the result remains inspectable

That means the launcher is not just for discovery. It is also for guided execution.
