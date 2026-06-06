# Lifecycle And Versions

## Purpose

Define how governed assets move through versioned ingestion, approval, update,
projection, and deletion.

The platform should treat every asset as a single governed entity with a
versioned lifecycle. The YAML files are the materialized representation of that
entity, not separate competing sources of truth.

## Core Principle

An asset has one canonical owner knowledge base and may be projected into
additional technical stores.

```text
canonical asset
  -> lives once in the repository model
  -> has version, status, ownership, and source refs
  -> may be projected to graph/vector/document/relational indexes
```

Projections are references or derived views. They are not the owner.

## Primary And Referenced Assets

The platform should distinguish between:

- primary or canonical assets
- referenced assets
- technical projections

### Primary Asset

The primary asset is the one governed record that owns the truth.

Examples:

```text
flow.loan_refinance
rule.refinance_eligibility
process.loan_refinance
tool.customer.read
entity.loan
```

The canonical asset:

- lives in one owner knowledge base
- has one active version at a time
- can be approved, deprecated, or deleted according to policy
- is the source from which projections are generated

### Referenced Asset

A referenced asset is not a second copy of the truth. It is a dependency or a
link to the primary asset.

Examples:

```text
process.loan_refinance
  related_to rule.refinance_eligibility type dependency
  related_to user_task.identify_customer type step
  related_to tool.customer.read type usage

flow.loan_refinance
  related_to process.loan_refinance type dependency
  related_to entity.loan type usage
```

Referenced assets should:

- point to a specific version or to the latest approved version, depending on policy
- be revalidated if the primary asset changes or is deleted
- show impact in diffs and previews before apply

### Projection

A projection is a technical copy or view used for search, graph, vector, or
runtime support.

Examples:

- Neo4j nodes for flow/process relationships
- Qdrant embeddings for search
- processed asset catalog rows
- audit/runtime state in relational storage

If a projection is removed, the primary asset should still exist in the owner
knowledge base.

## Version Model

Suggested fields:

- `asset_id`
- `asset_type`
- `version`
- `status`
- `owner`
- `source_refs`
- `relations`
- `payload`
- `created_at`
- `updated_at`
- `supersedes`
- `superseded_by`

## Versioning Rules

- New assets start at `1.0.0` unless a different policy is defined.
- Significant semantic changes should create a new version.
- Non-breaking metadata edits may advance a patch version.
- Draft changes should not overwrite approved history without trace.
- The system should retain the lineage of previous approved versions.

## Change Flow

```text
author draft
  -> validate
  -> compile
  -> compare with current approved version
  -> decide create new version or update draft
  -> write repository artifact
  -> sync projections
```

## Delete Semantics

Delete behavior must respect ownership and projection roles.

### Draft And Rejected Assets

- can be removed from the repository model
- projections should be refreshed
- related references should be revalidated

### Approved Assets

- should not disappear silently
- should either be tombstoned, deprecated, or require explicit approval
- dependent relations should be checked before removal
- projections should be updated to stop exposing the asset as active

## Relation Semantics

Relations should be version-aware.

Examples:

- a process may reference the latest approved version of a rule
- a flow may continue pointing to a deprecated process version until migrated
- a deleted asset should leave an auditable trace for dependent assets
- a referenced asset should display which primary asset version it depends on

Recommended relation states:

- `active`
- `deprecated`
- `superseded`
- `broken`
- `pending_review`

Recommended relation types:

- `dependency`
- `obligation`
- `optionality`
- `step`
- `transition`
- `usage`
- `explanation`

## Ingestion Iterations

Ingestion should be iterative:

1. scan corpus
2. extract candidates with LLM help
3. validate candidates
4. stage drafts
5. review changes
6. apply approved versions
7. sync projections

This lets the LLM help structure the assets while a human or policy layer
controls what actually becomes canonical.

## Projection Layers

The canonical repository can feed multiple projections:

- repository index
- graph projection
- semantic/vector projection
- document projection
- relational runtime or audit projection

If one projection is removed, the canonical asset should remain intact.

## Recommendation

Use versioned change sets instead of in-place destructive edits for approved
assets whenever possible. That makes lineage, rollback, and audit much easier.
