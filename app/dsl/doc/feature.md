# DSL Feature

## Purpose

Describe the first product slice of the asset DSL for business analysts,
knowledge engineers, and platform engineers.

This feature is the authoring layer for creating governed business assets with
a SQL-like language. It is designed for ingestion-time asset creation and
regeneration only.

## Product Idea

The business analyst writes statements like:

```text
CREATE KNOWLEDGE_BASE process_kb;
CREATE FLOW loan_refinance;
CREATE RULE refinance_eligibility;
CREATE PROCESS loan_refinance;
CREATE USER_TASK identify_customer;
CREATE TOOL customer.read;
CREATE ENTITY loan;
CREATE QA refinance_help;
```

The platform then:

1. Parses the DSL.
2. Validates ownership and relations.
3. Compares the change against the current approved version.
4. Compiles it into the current asset model.
5. Writes versioned repository artifacts.
6. Syncs the technical indexes.
7. Optionally triggers corpus-backed ingestion for full regeneration.

## Primary Users

- Business analyst
- Knowledge engineer
- Platform engineer
- Compliance or risk reviewer

## What The Business Analyst Gets

The analyst should be able to work in familiar business language instead of
editing raw YAML or JSON.

Expected interactions:

- create a rule with business conditions and actions
- create a flow that represents a customer intent
- create a process that composes approved tasks and tools
- create or update a knowledge base definition
- inspect the asset dictionary
- validate a draft before applying it
- delete draft or rejected assets
- regenerate governed assets from a raw corpus

## What The Platform Does

The platform acts as compiler and gatekeeper, not as a second source of truth.

It should:

- maintain one owner knowledge base per asset
- maintain version lineage for approved assets
- compile DSL statements into current repository artifacts
- enforce validation rules before apply
- let the LLM propose structure while a reviewer or policy layer controls apply
- preserve ingestion audit records
- refresh graph and search projections after apply

## Feature Scope

### In Scope

- SQL-like DSL for governed asset authoring
- asset dictionary browsing
- create, update, delete, validate, and preview actions
- ingestion-time knowledge creation
- knowledge base creation and regeneration from corpus
- VS Code integration for discoverability and validation

### Out Of Scope

- runtime ask flow behavior
- direct execution of banking operations
- replacing the existing repository model
- bypassing validation or approval gates

## End To End Flow

```text
Business analyst
  -> writes DSL
  -> validates in editor or API
  -> applies change set
  -> compiler emits asset artifacts
  -> validation service checks the result
  -> sync service updates indexes
  -> knowledge base and runtime consume the approved assets
```

## Knowledge Base Creation Flow

The DSL should support declarative creation of a knowledge base from a corpus
or from governed configuration.

```text
CREATE KNOWLEDGE_BASE process_kb
  FROM CORPUS 'data/raw/enterprise_dump_2026'
  APPLY EXTRACTION
  BUILD ASSETS;
```

This should map to:

- corpus scan
- document parsing
- extraction instructions
- asset generation
- version staging
- validation
- repository write
- sync and indexing

## Change Control Model

The LLM should be treated as a structuring assistant, not as the final owner of
truth.

- It can propose a draft asset shape.
- It can normalize fields and relations.
- It cannot bypass validation.
- It cannot overwrite approved lineage without a versioned change.

The human or policy layer should confirm:

- whether the draft becomes a new version
- whether the asset is deprecated or deleted
- whether relations need to be retargeted
- whether projections should be refreshed immediately or staged

## Why This Matters

The current platform already has strong ingestion, registry, and projection
logic. The DSL feature gives the business analyst a safer and more readable way
to author assets while keeping the current architecture intact.

It also makes the project easier to scale because new assets can be created
with a consistent syntax instead of handwritten repository files, while the
version history and reference graph stay intact.
