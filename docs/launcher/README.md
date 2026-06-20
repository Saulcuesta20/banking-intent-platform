# Enterprise AI Launcher

## Purpose

This folder contains the launcher-specific design documentation so it is easy to find and maintain in one place.

## Canonical Docs

- [Vision](./vision.md)
- [Architecture](./architecture.md)
- [Unified Catalog And AssetSet Roadmap](./unified-catalog-roadmap.md)
- [Implementation Tracker](./implementation-tracker.md)
- [Asset Editor Integration Plan](./asset-editor-integration-plan.md)
- [Components](./components.md)
- [Tech Stack](./tech-stack.md)
- [User Stories](./user-stories.md)
- [Commands](./commands.md)

## How To Read This Folder

Start with `vision.md` to understand the product intent and the must-have launcher features.
Then read `architecture.md` for the interaction model and system boundaries.
After that, use `components.md` and `tech-stack.md` to see what gets built and what tools support it.
Use `implementation-tracker.md` as the live handoff document for current status,
pending tasks, and decisions. Use `asset-editor-integration-plan.md` for the
current work to move asset editors inside the launcher shell. Finish with
`user-stories.md` and `commands.md` to understand the functional behavior and
how to operate the system.

## Summary

The Enterprise AI Launcher is the operational front door for the platform.
It should let users:

- browse flows and processes
- navigate application modules and submenus
- launch approved workflows
- chat with the platform
- inspect context and detail panels
- see live logs and traces
- review approvals and notifications

The launcher is a separate deployable frontend app inside the same monorepo. The canonical shell is built with React, TypeScript, and shadcn/ui, using shadcn-admin as a reference for app structure and admin-style interaction patterns.

The launcher shell owns the three-panel experience, chat workspace, navigation, and context panels. Dynamic editors are rendered inside the launcher experience and should not replace the shell or move the user into a separate app.
