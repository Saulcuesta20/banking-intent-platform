# Ontology Knowledge

## Purpose
Define how domain concepts are created during ingestion and projected during ask question.

## Responsibilities
- Extract domain concepts such as customer, savings account, loan, payment, disbursement, credit note, debit note, loan refinance, loan conditions, and customer conditions during ingestion.
- Store concepts as `ontology_nodes` and deterministic synonym maps as `ontology_aliases` on flow JSON.
- Store ontology concepts and synonym aliases in Neo4j as `Ontology` and `Synonym` nodes.
- Rank selected flow ontology nodes against the user question for explainability.
- Avoid creating ontology concepts dynamically during ask question.

## Main Components
- `OntologyAgent`
- `app.ontology.service.OntologyTermNormalizer`
- `CorpusFlowLoader.normalize_and_validate`
- `KnowledgeRecord.ontology_nodes`
- `KnowledgeRecord.ontology_aliases`
- `FlowAnswerContextService`

## Data Flow
Ingestion extracts and validates `ontology_nodes` on each flow. Deterministic
normalization then builds `ontology_aliases`, for example mapping the loan
concept to aliases such as `prestamo` and `credito`. Graph loading creates
`Ontology` nodes and linked `Synonym` nodes. During ask question, retrieval can
match either formal ontology nodes or synonym aliases. After a flow is selected,
`FlowAnswerContextService` reads the selected flow's nodes and ranks exact
node/alias matches before returning `related_ontology_nodes`.

## Example Input/Output
Input: `bajar la cuota de mi prestamo`

Output: `Loan`, `LoanRefinance`, `LoanConditions`, `Customer`.

## Interfaces
- `OntologyTermNormalizer.normalize_term(term)`
- `OntologyTermNormalizer.normalize_terms(terms)`
- `OntologyTermNormalizer.build_aliases_for_ontology_nodes(nodes)`
- `KnowledgeRecord.ontology_nodes`
- `KnowledgeRecord.ontology_aliases`
- `FlowAnswerContextService.build(question, record)`

## Implementation Notes
Runtime ontology behavior is projection and ranking over ingested nodes and
aliases. New terms are not created during ask question; they are normalized
during ingestion or query understanding.

## Future Replacement Strategy
Ontology extraction can become richer during ingestion through graph traversal, embeddings, or formal ontology tooling. Runtime should continue to project selected flow concepts unless a future use case requires broader ontology search.
