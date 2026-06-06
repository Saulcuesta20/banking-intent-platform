# Entity Vocabulary

## Purpose
Define how domain entities are created during ingestion and projected during ask
question.

`entity` is the business name. `concept` is the current compatibility name used
by code and existing data files.

## Responsibilities
- Extract domain entities such as customer, savings account, loan, payment,
  disbursement, credit note, debit note, loan refinance, loan conditions, and
  customer conditions during ingestion.
- Treat prior `concept` values as entity values.
- Store entities in the current flow YAML fields `concepts` and
  `concept_aliases` until the code/data migration renames them.
- Store entities and synonyms in Neo4j using the current `Concept` and
  `Synonym` labels until graph labels are migrated.
- Rank selected flow entities against the user question for explainability.
- Avoid creating entities dynamically during ask question.

## Main Components
- `ConceptAgent` currently acts as the entity extraction agent.
- `app.knowledge_base.vocabulary.ConceptVocabulary` currently normalizes entity
  names and synonyms.
- `CorpusFlowLoader.normalize_and_validate`
- `KnowledgeRecord.concepts`
- `KnowledgeRecord.concept_aliases`
- `AnswerBuilder`

## Data Flow
Ingestion extracts and validates entity names on each flow. Today those values
are stored as `concepts`. Normalization loads the synonym catalog from
`config/knowledge_base/concept_aliases.yaml` or `CONCEPT_ALIAS_CATALOG_PATH`, then
builds `concept_aliases`.

Graph loading currently creates `Concept` nodes and linked `Synonym` nodes.
During ask question, retrieval can match either the canonical entity name or any
synonym. After a flow is selected, `AnswerBuilder` reads the selected flow's
entity values and ranks exact node/synonym matches before returning
`related_concepts`.

Compatibility mapping:

```text
Business term      Current code/data name
-------------      ----------------------
entity             concept
entity synonyms    concept_aliases
EntityVocabulary   ConceptVocabulary
Entity node        Concept node
has_synonym        HAS_SYNONYM
related_entities   related_concepts
```

## Entity And Synonym Model
An entity is the canonical business meaning. A synonym is an alternate label,
phrase, spelling, or language variant for that same entity.

```text
entity.loan
  synonyms:
    - prestamo
    - credito
    - loan

entity.customer
  synonyms:
    - cliente
    - titular
    - usuario

entity.savings_account
  synonyms:
    - cuenta
    - cuenta ahorro
    - cuenta de ahorros
    - savings account
```

Entity relationships are separate from synonyms:

```text
entity.loan_refinance
  related_to -> entity.loan
  uses -> entity.loan_conditions
  governed_by -> business_rule.refinance_eligibility

entity.payment
  related_to -> entity.account
  related_to -> entity.transaction
```

A synonym answers "what other words mean this entity?" A relationship answers
"how is this entity connected to another business thing?"

## Example Input/Output
Input: `bajar la cuota de mi prestamo`

Output entities:

```text
Loan
LoanRefinance
LoanConditions
Customer
```

Output synonyms may include:

```text
prestamo -> Loan
credito -> Loan
cuota -> LoanConditions
refinanciacion -> LoanRefinance
```

## Interfaces
- `ConceptVocabulary.normalize_term(term)`
- `ConceptVocabulary.normalize_terms(terms)`
- `ConceptVocabulary.build_aliases_for_concepts(nodes)`
- `KnowledgeRecord.concepts`
- `KnowledgeRecord.concept_aliases`
- `AnswerBuilder.build(question, record)`

These names are intentionally listed as current implementation names. Future
code migration can introduce `EntityVocabulary`, `KnowledgeRecord.entities`,
`entity_aliases`, and `related_entities` while keeping backwards compatibility.

## Implementation Notes
Runtime entity behavior is projection and ranking over ingested names and
synonyms. New entities are not created during ask question; they are normalized
during ingestion or question understanding. Synonym vocabulary is maintained as
data, not hardcoded in Python.

Entities belong to the business model knowledge base. Flows and processes
reference them.

## Current Implementation Status
Implemented now:

- Flow record has `concepts`.
- Flow record can have `concept_aliases`.
- `ConceptVocabulary` builds aliases from
  `config/knowledge_base/concept_aliases.yaml`.
- Neo4j stores `(:Concept)-[:HAS_SYNONYM]->(:Synonym)`.
- Ask traces expose `related_concepts`.

Not migrated yet:

- Field rename from `concepts` to `entities`.
- Neo4j label rename from `Concept` to `Entity`.
- Result rename from `related_concepts` to `related_entities`.

## Future Replacement Strategy
Entity extraction can become richer during ingestion through graph traversal,
embeddings, or formal ontology tooling. Runtime should continue to project
selected flow entities unless a future use case requires broader entity search.
