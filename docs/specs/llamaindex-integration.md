# LlamaIndex Integration

## Purpose
Use LlamaIndex as an optional retrieval provider inside the retrieval component.

## Responsibilities
- Load flow files and user task files.
- Build indexes for retrieval.
- Return context snippets without coupling domain logic to LlamaIndex types.

## Main Components
- A future document-index adapter behind `app/knowledge_graph/providers.py::KnowledgeGraphRepository`
- Document parser registry
- Index configuration

## Data Flow
Flow records are converted into documents, LlamaIndex indexes them, and retrieval returns context for concepts and intent services.

## Example Input/Output
Input: OpenAPI or flow JSON describing loan refinance.

Output: retrieved context mentioning loan refinance event, actions, and tasks.

## Interfaces
- `app/knowledge_graph/providers.py::KnowledgeGraphRepository`

## Implementation Notes
The default ask path uses Neo4j in `app/knowledge_graph/neo4j.py`. A future LlamaIndex experiment should implement the `KnowledgeGraphRepository` port without adding a second runtime component.

## Future Replacement Strategy
GraphRAG is implemented separately in `app/knowledge_graph/neo4j.py` for Neo4j-backed retrieval. Haystack, LlamaIndex, or custom retrieval can replace either retrieval provider behind the same port.
