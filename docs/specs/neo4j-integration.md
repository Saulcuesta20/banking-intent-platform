# Neo4j Integration

## Purpose
Use Neo4j as the first graph database for banking knowledge.

## Responsibilities
- Store concept, synonym, intent, event, user task, and action nodes.
- Store relationships for explainability.
- Support graph lookup during question answering.

## Main Components
- Neo4j driver adapter
- Cypher mapper
- Graph repository interface
- Docker Compose service

## Data Flow
Ingested records are converted to Cypher upserts. `app/knowledge_graph/neo4j.py` queries Neo4j to build GraphRAG context for LangChain and the LLM.

## Example Input/Output
Input record: `loan_refinance.flow.json`

Output graph paths include `Flow -> UserTask -> Action`, where `Action.type` is
`front_action` or `back_action`, and `Flow -> Concept -> Synonym`, where
`Synonym.term` contains normalized aliases such as `credito` or `prestamo`.

## Interfaces
- `KnowledgeGraphRepository.upsert_record(record)`
- `KnowledgeGraphRepository.find_related(intent)`

## Implementation Notes
Neo4j credentials are environment-driven. Inside Docker, application containers connect with `bolt://neo4j:7687`; host scripts connect with `bolt://localhost:7687`. Runtime ask requires Neo4j-backed GraphRAG retrieval.

## Future Replacement Strategy
Another graph provider can replace Neo4j if it implements graph repository methods and relationship semantics.
