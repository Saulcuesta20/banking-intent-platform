# LlamaIndex Integration

## Purpose
Use LlamaIndex as an optional retrieval provider inside the retrieval component.

## Responsibilities
- Load flow files and user task files.
- Build technical indexes for retrieval.
- Return context snippets without coupling domain logic to LlamaIndex types.
- Avoid becoming an owner knowledge base for assets.

## Main Components
- A future document-index adapter behind `app/knowledge_base/ports.py::KnowledgeBaseRepository`
- Document parser registry
- Index configuration

## Data Flow
Approved owner-KB assets are converted into documents, LlamaIndex indexes them,
and retrieval returns context for entities and intent services. The index is a
search surface; asset lifecycle and approval stay in the owner KB.

## Example Input/Output
Input: OpenAPI or flow YAML describing loan refinance.

Output: retrieved context mentioning loan refinance event, tools, and tasks.

## Interfaces
- `app/knowledge_base/ports.py::KnowledgeBaseRepository`

## Implementation Notes
The default ask path uses Neo4j in
`app/knowledge_base/adapters/graph/neo4j.py`. A future LlamaIndex experiment
should implement the `KnowledgeBaseRepository` port without adding a second
runtime component.

## Future Replacement Strategy
GraphRAG is implemented in `app/knowledge_base/adapters/graph/neo4j.py` for
Neo4j-backed retrieval. Haystack, LlamaIndex, or custom retrieval can replace
the retrieval adapter behind the same port.
