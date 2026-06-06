# Knowledge Base Graph Adapter

## Purpose
Represent approved banking asset relationships in a graph database as a
technical index.

## Responsibilities
- Index entities, synonyms, intents, user tasks, frontend tools, back tools, business events, and relationships.
- Provide the bounded knowledge context used by GraphRAG and the LLM.
- Use Neo4j as the first graph database.
- Avoid becoming the owner knowledge base for assets.

## Main Components
- Knowledge-base repository port
- Neo4j graph adapter
- Node and relationship mappers
- Query service

## Data Flow
Ingestion creates records, entity synonym maps, and an tool registry. Graph
loading maps approved owner-KB assets to nodes and relationships. GraphRAG
retrieval queries flows, tasks, tools, utterances, entities, and synonym
aliases for constrained LLM reasoning.

## Example Input/Output
Input node: `loan.refinance`

Output neighbors: `LoanRefinancingRequested`, `Loan`, `Synonym(prestamo)`, `Synonym(credito)`, `LoanConditions`, `refinance.proposal.prepare`.

## Interfaces
- `KnowledgeBaseRepository.upsert_record(record)`
- `KnowledgeBaseRepository.search(search_terms)`
- `KnowledgeBaseService.search(search_terms)`

## Implementation Notes
The MVP includes Neo4j graph loading and GraphRAG retrieval for the default ask
flow. Runtime ask requires graph-backed retrieval so the LLM classifies only
against approved graph candidates. Neo4j is a relationship/search surface, not
the lifecycle owner of flows, rules, tasks, tools, or entities.

## Future Replacement Strategy
Graph storage can move to another graph database if the repository interface is preserved.
