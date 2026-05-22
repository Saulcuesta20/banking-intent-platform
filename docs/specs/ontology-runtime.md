# Ontology Knowledge

## Purpose
Define how domain concepts are created during ingestion and projected during ask question.

## Responsibilities
- Extract domain concepts such as customer, savings account, loan, payment, disbursement, credit note, debit note, loan refinance, loan conditions, and customer conditions during ingestion.
- Store concepts as `ontology_nodes` on flow JSON and Neo4j graph nodes.
- Rank selected flow ontology nodes against the user question for explainability.
- Avoid creating ontology concepts dynamically during ask question.

## Main Components
- `OntologyAgent`
- `CorpusFlowLoader.normalize_and_validate`
- `KnowledgeRecord.ontology_nodes`
- `FlowAnswerContextService`

## Data Flow
Ingestion extracts and validates `ontology_nodes` on each flow. During ask question, `FlowAnswerContextService` reads the selected flow's nodes and lightly ranks exact text matches before returning `related_ontology_nodes`.

## Example Input/Output
Input: `bajar la cuota de mi prestamo`

Output: `Loan`, `LoanRefinance`, `LoanConditions`, `Customer`.

## Interfaces
- `KnowledgeRecord.ontology_nodes`
- `FlowAnswerContextService.build(question, record)`

## Implementation Notes
The older `OntologyService` runtime package was removed from the active codebase. Runtime ontology behavior is projection and ranking over ingested nodes.

## Future Replacement Strategy
Ontology extraction can become richer during ingestion through graph traversal, embeddings, or formal ontology tooling. Runtime should continue to project selected flow concepts unless a future use case requires broader ontology search.
