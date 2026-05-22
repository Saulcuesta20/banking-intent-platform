# Knowledge Graph

## Purpose
Represent banking knowledge and relationships in a graph database.

## Responsibilities
- Store ontology nodes, ontology synonym aliases, intents, user tasks, front actions, back actions, business events, and relationships.
- Provide the bounded knowledge context used by GraphRAG and the LLM.
- Use Neo4j as the first graph database.

## Main Components
- Graph repository port
- Neo4j graph adapter
- Node and relationship mappers
- Query service

## Data Flow
Ingestion creates records, ontology alias maps, and an action registry. Graph
loading maps records to nodes and relationships. GraphRAG retrieval queries
flows, tasks, actions, utterances, ontology nodes, and synonym aliases for
constrained LLM reasoning.

## Example Input/Output
Input node: `loan.refinance`

Output neighbors: `LoanRefinancingRequested`, `Loan`, `Synonym(prestamo)`, `Synonym(credito)`, `LoanConditions`, `refinance.proposal.prepare`.

## Interfaces
- `GraphRepository.upsert_record(record)`
- `GraphRepository.find_related(intent)`
- `GraphRepository.search_concepts(text)`

## Implementation Notes
The MVP includes Neo4j graph loading and GraphRAG retrieval for the default ask flow. Runtime ask requires graph-backed retrieval so the LLM classifies only against approved graph candidates.

## Future Replacement Strategy
Graph storage can move to another graph database if the repository interface is preserved.
