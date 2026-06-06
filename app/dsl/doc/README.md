# DSL Design Notes

This folder holds the idea space for the asset DSL and its VS Code extension.
It is intentionally separate from the main project specifications so the
proposal can evolve without mixing into runtime documentation.

## Scope

The DSL is an authoring layer for enterprise assets.

- It is SQL-like.
- It maps to the governed asset registry.
- It compiles into the current YAML/JSON and repository model.
- It applies only to ingestion-time creation and regeneration of knowledge.
- It does not replace ask/runtime behavior.

## Documents

- [Feature](./feature.md)
- [User Stories](./user-stories.md)
- [Architecture](./architecture.md)
- [Versioning](./versioning.md)
- [Knowledge Base](./knowledge-base.md)
- [Examples](./examples.md)
- [Rule](./rule.md)
- [Flow](./flow.md)
- [Process](./process.md)
- [User Task](./user-task.md)
- [Tool](./tool.md)
- [Entity](./entity.md)
- [QA](./qa.md)

## Design Rule

Every asset remains owned by one canonical knowledge base. The DSL is only a
friendly way to author and manage those assets, not a second source of truth.
