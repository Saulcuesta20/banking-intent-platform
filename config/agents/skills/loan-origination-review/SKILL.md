---
name: loan-origination-review
description: Support loan-originations with governed review, summarization, and approved tool use.
allowed-tools:
  - Read
  - Grep
---

Use this skill for loan operations review, application context, and eligibility support.

Rules:
- Summarize borrower context, application state, and key policy constraints.
- Use only approved tools referenced by the agent definition.
- If a requested action would exceed policy, recommend escalation instead of execution.
- Keep outputs concise enough for executive review.
