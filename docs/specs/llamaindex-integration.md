# LlamaIndex Integration

## Purpose
Use LlamaIndex as an optional retrieval provider inside the retrieval component.

## Responsibilities
- Load flow files and user task files.
- Build indexes for retrieval.
- Return context snippets without coupling domain logic to LlamaIndex types.

## Main Components
- `app/retrieval/ai.py::LlamaIndexKnowledgeRetrievalProvider`
- Document parser registry
- Index configuration

## Data Flow
Flow records are converted into documents, LlamaIndex indexes them, and retrieval returns context for ontology and intent services.

## Example Input/Output
Input: OpenAPI or flow JSON describing loan refinance.

Output: retrieved context mentioning loan refinance event, actions, and tasks.

## Interfaces
- `app/retrieval/providers.py::KnowledgeRetrievalProvider`

## Implementation Notes
The default ask path now uses Neo4j GraphRAG in `app/retrieval/graph.py`. The LlamaIndex adapter boundary remains available in `app/retrieval/ai.py` for future vector or document-index retrieval experiments.

## Future Replacement Strategy
GraphRAG is implemented separately in `app/retrieval/graph.py` for Neo4j-backed retrieval. Haystack, LlamaIndex, or custom retrieval can replace either retrieval provider behind the same port.
