---
name: delegation
description: Route work to a specialist agent or approved tool-backed capability.
allowed-tools:
  - Read
  - Grep
---

Use this skill when a request should be handed off to a more specific agent or capability.

Rules:
- Choose the narrowest agent that can safely handle the task.
- Preserve traceability for every handoff.
- Do not invent tools or capabilities outside the catalog.
- Return the reason for delegation in one short, auditable sentence.
