# Concept Vocabulary

## Purpose
Define how domain concepts are created during ingestion and projected during ask question.

## Responsibilities
- Extract domain concepts such as customer, savings account, loan, payment, disbursement, credit note, debit note, loan refinance, loan conditions, and customer conditions during ingestion.
- Store concepts as `concepts` and data-driven synonym maps as `concept_aliases` on flow JSON.
- Store concepts and synonym aliases in Neo4j as `Concept` and `Synonym` nodes.
- Rank selected flow concepts against the user question for explainability.
- Avoid creating concepts dynamically during ask question.

## Main Components
- `ConceptAgent`
- `app.knowledge_graph.vocabulary.ConceptVocabulary`
- `CorpusFlowLoader.normalize_and_validate`
- `KnowledgeRecord.concepts`
- `KnowledgeRecord.concept_aliases`
- `AnswerBuilder`

## Data Flow
Ingestion extracts and validates `concepts` on each flow. Normalization
loads the synonym catalog from `data/concept/term_synonyms.json` or
`ONTOLOGY_SYNONYM_CATALOG_PATH`, then builds `concept_aliases`. Graph loading creates
`Concept` nodes and linked `Synonym` nodes. During ask question, retrieval can
match either formal concepts or synonym aliases. After a flow is selected,
`AnswerBuilder` reads the selected flow's nodes and ranks exact
node/alias matches before returning `related_concepts`.

## Example Input/Output
Input: `bajar la cuota de mi prestamo`

Output: `Loan`, `LoanRefinance`, `LoanConditions`, `Customer`.

## Interfaces
- `ConceptVocabulary.normalize_term(term)`
- `ConceptVocabulary.normalize_terms(terms)`
- `ConceptVocabulary.build_aliases_for_concepts(nodes)`
- `KnowledgeRecord.concepts`
- `KnowledgeRecord.concept_aliases`
- `AnswerBuilder.build(question, record)`

## Implementation Notes
Runtime concept behavior is projection and ranking over ingested nodes and
aliases. New terms are not created during ask question; they are normalized
during ingestion or question understanding. Synonym vocabulary is maintained as
data, not hardcoded in Python.

## Future Replacement Strategy
Concept extraction can become richer during ingestion through graph traversal, embeddings, or formal concept tooling. Runtime should continue to project selected flow concepts unless a future use case requires broader concept search.
