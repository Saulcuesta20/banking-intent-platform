# Neo4j Integration

## Purpose
Use Neo4j as the first graph database for approved banking relationships and
GraphRAG context.

## Responsibilities
- Index entity/concept, synonym, intent, event, user task, and tool nodes.
- Store relationships for explainability.
- Support graph lookup during question answering.
- Keep asset ownership in the configured owner knowledge bases.

## Main Components
- Neo4j driver adapter
- Cypher mapper
- Graph repository interface
- Docker Compose service

## Data Flow
Ingested records are converted to Cypher upserts.
`app/knowledge_base/adapters/graph/neo4j.py`
queries Neo4j to build GraphRAG context for LangChain and the LLM. Neo4j stores
relationship/index state; it does not own the asset lifecycle.

## Example Input/Output
Input record: `loan_refinance.flow.yaml`

Output graph paths include `Flow -> UserTask -> Tool`, where `Tool.tool_type` is
`frontend_tool` or `backend_tool`, and currently `Flow -> Concept -> Synonym`, where
`Synonym.term` contains normalized aliases such as `credito` or `prestamo`.
`Concept` is the current graph label for the canonical business entity.

## Interfaces
- `KnowledgeBaseRepository.upsert_record(record)`
- `KnowledgeBaseRepository.search(search_terms)`

## Implementation Notes
Neo4j credentials are environment-driven. Inside Docker, application containers connect with `bolt://neo4j:7687`; host scripts connect with `bolt://localhost:7687`. Runtime ask requires Neo4j-backed GraphRAG retrieval.

## Future Replacement Strategy
Another graph provider can replace Neo4j if it implements graph repository methods and relationship semantics.
