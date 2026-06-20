# Ontology Search Spaces

## Purpose

Define the target ontology shape for faster ingest and ask retrieval without
creating one flat, unbounded graph.

This is a preparation spec. It records agreed implementation direction, not
completed behavior.

## Core Decisions

- `semantic_space` replaces `domain` as the business/search context asset.
- `business_layer` should be renamed to `structural_layer`.
- `entity_role` should be removed as a primary field because it duplicates the
  structural layer. Keep only temporary backward compatibility while migrating.
- `concept` remains a legacy alias for `entity`; new extraction should emit
  `entity`.
- Do not add `dimension`, `metric`, `data_asset`, or `evidence_bundle` asset
  types in the next implementation phase.
- Evidence should be emitted as JSON on assets, ask traces, or answer payloads,
  not as a governed asset type.
- Synonyms and aliases should live in the ontology graph as alias metadata /
  properties for entities and structural layers, not in a standalone YAML
  synonym catalog.
- `subtype` stores the business/structural stereotype inside a layer.
- `technical_type` stores the technical implementation form. It is not the same
  as `subtype`; for example, a resource can be `subtype: table` and
  `technical_type: table`.
- Table columns, IDs, and ordinary data attributes are properties of an entity,
  not graph nodes by default.
- `business_resource` is the structural layer for enterprise resources. Do not
  use `asset` as a structural layer name because `asset_type` already means a
  governed platform asset type.
- Structural subtypes such as `party.customer`, `party.prospect`, or
  `organization.department` should be stored as `subtype` values by default,
  not as graph nodes or relationships.

## Target Fields

Canonical entity shape:

```yaml
asset_type: entity
id: entity.loan_application
name: Solicitud de préstamo
structural_layer: transaction
subtype: application
aliases:
  - solicitud de crédito
  - aplicación de préstamo
attributes:
  application_id:
    type: string
    identifier: true
  status:
    type: string
relations:
  - type: governed_by
    target: business_rule.credit_policy
evidence:
  - source_asset_id: document.credit_policy_2026
    source_ref: section_4_2
    confidence: 0.91
```

Table-as-entity shape:

```yaml
asset_type: entity
id: entity.gold_customers
name: gold.customers
structural_layer: business_resource
subtype: table
technical_type: table
represents:
  - entity.customer
attributes:
  customer_id:
    type: string
    identifier: true
  credit_score:
    type: integer
```

Semantic space shape:

```yaml
asset_type: semantic_space
id: semantic_space.credit_risk
name: Riesgo de crédito
route_hints:
  - crédito
  - préstamo
  - score
  - rechazo
structural_layers:
  - party
  - transaction
  - agreement
  - business_resource
allowed_asset_types:
  - entity
  - flow
  - process
  - business_rule
  - document
  - causality
retrieval_policy:
  graph_depth: 2
  allowed_owner_kbs:
    - business_model_kb
    - rules_kb
    - causality_kb
    - document_kb
    - process_kb
```

## Text Graph By Search Layers

The graph should be navigated through search layers rather than queried as one
flat graph:

```text
Layer 0: semantic_space
  semantic_space.credit_risk
    -> CONTAINS_CONTEXT -> entity.loan_application
    -> CONTAINS_CONTEXT -> business_rule.credit_policy
    -> CONTAINS_CONTEXT -> causality.income_volatility_rejects_application

Layer 1: structural_layer
  structural_layer.party
    aliases: [party, data_master, datamaster, catalog]
    subtypes: [customer, prospect, vendor, regulator, partner]
    -> classifies -> entity.customer
    -> classifies -> entity.payroll_customer

  structural_layer.organization
    subtypes: [division, department, team, committee, region]
    -> classifies -> entity.retail_lending_department

  structural_layer.capability
    subtypes: [center_of_excellence, shared_service, practice, competency]
    -> classifies -> entity.loan_origination_capability

  structural_layer.transaction
    subtypes: [application, payment, transfer, claim, order]
    -> classifies -> entity.loan_application
    -> classifies -> entity.payment

  structural_layer.agreement
    subtypes: [contract, policy, terms, consent]
    -> classifies -> entity.credit_policy

  structural_layer.business_resource
    subtypes: [system, platform, document, dataset, table, tool]
    -> classifies -> entity.gold_customers
    -> classifies -> entity.risk_model

Layer 2: asset_type
  entity.loan_application
  business_rule.credit_decision_policy
  flow.loan_refinance
  process.loan_origination
  document.credit_policy_2026
  causality.income_volatility_rejects_application

Layer 3: graph neighborhood
  entity.loan_application
    -> governed_by -> business_rule.credit_decision_policy
    -> affected_by -> causality.income_volatility_rejects_application
    -> uses -> entity.credit_score
    -> represented_by -> entity.gold_loan_applications

Layer 4: properties
  entity.gold_loan_applications
    -> represents -> entity.loan_application
  entity.gold_loan_applications.attributes.application_id.identifier = true
  entity.gold_loan_applications.attributes.credit_score.type = integer
  entity.gold_loan_applications.technical_type = table

Layer 5: evidence JSON
  answer.evidence[]
  asset.payload.evidence[]
  ask_trace.evidence[]
```

## Ask Routing Examples

Question: `Quiero refinanciar mi préstamo`

```text
semantic_space: loan_origination
structural_layers: transaction, offering, agreement
asset_types: flow, process, business_rule, user_task
retrieval: select executable route and required policy constraints
```

Question: `¿Quién aprueba excepciones de crédito?`

```text
semantic_space: credit_risk
structural_layers: organization, workforce_role, agreement
asset_types: entity, business_rule, document
retrieval: find approval roles, org owners, and governing policy evidence
```

Question: `¿De dónde sale customer_id?`

```text
semantic_space: customer_360
structural_layers: party, business_resource
asset_types: entity
retrieval: inspect table entity properties and representation metadata
```

Question: `¿Por qué se bloquea una transferencia?`

```text
semantic_space: payments
structural_layers: transaction, agreement, event
asset_types: business_rule, causality, process, document
retrieval: find rules, causes, process states, and evidence JSON
```

Question: `¿Qué productos ofrece banca digital?`

```text
semantic_space: digital_banking
structural_layers: portfolio, offering, channel
asset_types: entity, flow, document
retrieval: list offerings by portfolio and channel context
```

## Ingest TODO

- Add `semantic_space` to the asset registry and extraction schema.
- Treat `domain` as a legacy compatibility field and migrate usages toward
  `semantic_space`.
- Rename `business_layer` to `structural_layer` across extraction, catalog,
  API payloads, launcher ontology rendering, `kb stats`, and graph projection.
- Stop emitting `entity_role` from new extraction. Preserve read compatibility
  only while old data exists.
- Replace `concept` extraction with canonical `entity` extraction.
- Move synonym authority from `config/knowledge_base/concept_aliases.yaml` into
  graph/catalog entity alias data.
- Keep alias data simple: entity `aliases` plus graph alias lookup. Do not add a
  separate synonym YAML catalog in the target architecture.
- Add `technical_type` support first for `table` entities, keeping
  `subtype` as the structural stereotype and `technical_type` as the technical
  implementation form.
- Keep table columns, IDs, and attributes inside `entity.attributes` unless an
  attribute is promoted manually to a governed entity.
- Use `represented_by` / `represents` as the canonical business-to-technical
  mapping relation. Treat `materializes` / `materialized_in` as legacy aliases.
- Persist evidence as JSON arrays on assets and ask traces.
- Rename the current universal ontology structural layer `asset` to
  `business_resource`, and treat old `asset` layer values as migration aliases.
- Store structural subtypes as entity `subtype` values by default:
  `structural_layer=party, subtype=customer`, not as `party.customer` graph
  nodes.

## Ask TODO

- Add a semantic-space selection step before broad graph/vector retrieval.
- Filter graph and vector retrieval by `semantic_space`, `structural_layer`,
  `asset_type`, owner KB, and approval status.
- Use aliases from entity graph data for query expansion instead of the YAML
  synonym catalog.
- Include selected `semantic_space`, `structural_layers`, assets consulted, and
  evidence JSON in ask trace output.
- Keep runtime ask read-only over approved assets. Ask must not create entities,
  spaces, aliases, or routes.
