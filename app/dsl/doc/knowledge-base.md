# Knowledge Base DSL

## Purpose

Model the creation of owner knowledge bases and the indexes they feed.

The goal is to express the idea of a knowledge base in a declarative way,
similar to how MindsDB lets users declare data sources and knowledge bases.

## Concept

```text
CREATE KNOWLEDGE_BASE process_kb
  USING 'process'
  STORES ('repository', 'graph')
  DESCRIPTION 'Flow and process ownership';
```

This should not create an isolated runtime store. It should create a
governed configuration that drives ingestion and asset ownership.
The canonical asset still lives once in the repository model and is then
projected to technical stores.

## Primary And Referenced Storage

The owner knowledge base stores the primary asset record.

The other stores keep references or projections:

- repository store: canonical definition and lineage
- graph store: relationships and traversal
- vector store: semantic retrieval
- document store: long-form source evidence
- relational store: runtime or audit state

Example:

```text
process_kb
  owns -> flow.loan_refinance
  owns -> process.loan_refinance
  projects -> Neo4j
  projects -> Qdrant
```

```text
rules_kb
  owns -> rule.refinance_eligibility
  projects -> repository
  projects -> graph
```

If a technical store disappears, the canonical asset remains in its owner KB.
If a canonical asset is deleted or deprecated, the projections must be
refreshed so the references stop advertising it as active.

## Asset Catalog Shape

The DSL should compile into the unified asset catalog, which today is stored in
`asset_catalog.sqlite`.

Current catalog fields include:

- `asset_id`
- `asset_type`
- `name`
- `version`
- `status`
- `primary_kb`
- `stores`
- `payload`
- `updated_at`

Meaning:

- `primary_kb` is the main knowledge base that owns the asset in the catalog.
- `stores` is the set of technical knowledge bases or projections used for that
  asset type.
- `payload` is the full normalized asset document, including relations,
  source refs, and any type-specific metadata.

Types:

| Column | Type | Meaning |
|---|---|---|
| `asset_id` | `TEXT` | Global unique asset id. |
| `asset_type` | `TEXT` | Logical type such as `flow`, `process`, `rule`, `qa`, `tool`, `entity`. |
| `name` | `TEXT` | Human-readable asset name. |
| `version` | `TEXT` | Version label, currently string-based. |
| `status` | `TEXT` | Asset lifecycle state such as `draft`, `approved`, or `deprecated`. |
| `primary_kb` | `TEXT` | Canonical owner knowledge base. |
| `stores` | `TEXT[]` conceptually, stored as JSON text in SQLite | Technical stores/projections for the asset type. |
| `payload` | `JSON` conceptually, stored as JSON text in SQLite | Full normalized asset document. |
| `updated_at` | `TEXT` | Last update timestamp in SQLite CURRENT_TIMESTAMP format. |

Example:

```text
asset_id: rule.refinance_eligibility
asset_type: rule
primary_kb: rules_kb
stores: [repository, document, graph, vector]
```

That means:

- the canonical rule is owned by `rules_kb`
- the asset is materialized in the repository catalog
- supporting evidence can appear in `document`
- relation traversal can appear in `graph`
- semantic retrieval can appear in `vector`

Example of a flow:

```text
asset_id: flow.loan_refinance
asset_type: flow
primary_kb: process_kb
stores: [repository, graph, vector]
```

The catalog does not create a second truth layer. It is the unified inventory
of all governed assets plus the stores they are projected into.

## Example Statements

```text
CREATE KNOWLEDGE_BASE process_kb;
CREATE KNOWLEDGE_BASE rules_kb;
CREATE KNOWLEDGE_BASE business_model_kb;
CREATE KNOWLEDGE_BASE qa_kb;
CREATE KNOWLEDGE_BASE document_kb;
CREATE KNOWLEDGE_BASE config_kb;
```

## Expected Behavior

- registers the owner KB
- defines which asset types it owns
- defines which technical stores can project it
- configures validation and routing rules
- tracks versioned lineage for assets owned by the KB

## Ingestion Role

Knowledge base creation happens before asset generation and can also trigger a
corpus-backed build:

```text
CREATE KNOWLEDGE_BASE process_kb
  USING 'process'
  FROM CORPUS 'data/raw/enterprise_dump_2026'
  APPLY EXTRACT_INSTRUCTIONS
  BUILD ASSETS;
```

That statement is shorthand for the current extraction, normalization,
version staging, validation, repository write, and sync pipeline.
