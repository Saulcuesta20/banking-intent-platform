# Knowledge Base

## Purpose
Define the canonical component that owns enterprise knowledge-base access,
search, validation, synchronization, vocabulary, and storage adapters.

`knowledge_base` replaces `knowledge_graph` as the component boundary. A graph
database is now one adapter type, not the whole knowledge component.

## Responsibilities
- Load approved owner-KB assets from file/YAML/JSON sources.
- Expose asset registry, asset repository, asset search, validation, and sync.
- Normalize entity vocabulary and synonyms.
- Provide a `KnowledgeBaseService` boundary for runtime retrieval and ingestion.
- Route retrieval to the right knowledge sources after the ask/goal router
  decides what the user needs.
- Build an `EvidenceBundle` that records the sources and evidence used by ask.
- Host storage adapters for graph, vector, NoSQL/document, relational, and file
  stores.
- Keep graph/vector/search databases as technical indexes, not asset owners.

## Package Layout

```text
app/knowledge_base/
  models.py
  registry.py
  loader.py
  repository.py
  search.py
  service.py
  source_router.py
  ports.py
  sync.py
  validation.py
  vocabulary.py
  asset_adapters.py

  adapters/
    file/
      yaml_json.py
    graph/
      neo4j.py
    vector/
      qdrant.py
    nosql/
      document_store.py
    relational/
      postgres.py
```

## Knowledge Views

`KnowledgeRepository` is the source of truth for approved assets. `Knowledge
Views` are query-friendly ways to read the same governed knowledge at runtime.
They are not separate owners of the asset.

| View | Current/Future Store | Runtime Role |
|---|---|---|
| Repository View | YAML/JSON repository | Approved asset definitions and lifecycle state. |
| Graph View | Neo4j | Relationships between flows, processes, tasks, tools, rules, and entities. |
| Vector View | Qdrant | Semantic retrieval over text, rules, policies, Q&A, and documents. |
| Document View | NoSQL/document store | Long documents, policy pages, manuals, and corpus chunks. |
| Relational View | Postgres/RDBMS | Runtime state, audit, decisions, approvals, and monitoring. |
| External API View | Tools/adapters | Real-time evidence such as sanctions or external validations. |

## Knowledge Source Router

`KnowledgeSourceRouter` does not replace the ask/goal router. The ask/goal
router decides what the user needs; the knowledge source router decides where
to look for evidence.

```text
Question
  -> QuestionUnderstanding
  -> Ask/Goal Router
       Q&A directa
       selección de flujo
       explicación de proceso
       ejecución operativa
       múltiples intenciones complementarias
       aclaración requerida
  -> KnowledgeSourceRouter
       qa
       rules_policies
       process_flows
       entities
       configurations
       tools_apis
  -> Knowledge Views
       repository
       graph
       vector
       document
       relational
       external_api
  -> EvidenceBundle
```

## Operator Query Command

`kb query --text "..."` is the high-level command for consulting the knowledge
base as a logical engine. It should be used before reaching for physical
database commands because it shows the source routes, matched repository
assets, graph evidence when available, and the current status of vector,
document, and relational adapters.

```bash
kb query --asset-type flow --text "refinanciamiento"
kb query --asset-type business_rule --text "pago automatico"
kb query --asset-type tool --kb graph --format json
kb query --asset-type plan --owner-kb planning_kb --text "cobranza preventiva"
kb query --asset-type causality --relation-type has_effect --text "mora"
kb query --owner-kb business_model_kb --asset-type entity --text "prestamo"
```

`kb query` reads the asset-type registry and returns the logical owner KB plus
the configured technical stores. For example, `--asset-type flow` maps to owner
KB `process_kb` and can report repository, graph, and vector engines because
those are the stores declared for `flow` in
`config/asset_registry/asset_types.yaml`.

The lower-level commands remain useful for adapter debugging:

- `kb query --kb repository` inspects the governed asset repository.
- `kb query --kb graph` inspects Neo4j-oriented relationship retrieval.
- `ask "..." --debug-trace` prints the evidence-bearing ask trace and is the quickest way to inspect the bundle shape consumed by ask.

## Evidence Bundle

`EvidenceBundle` is the auditable package produced before planning and answer
generation. It records:

- selected knowledge source routes
- views consulted or expected
- matched flow/process records
- matched approved assets
- source metadata such as confidence, source refs, versions, or API evidence

The current implementation builds this bundle from graph search records and
asset search results. Future adapters should add richer snippets, effective
dates, versions, and external API responses.

## Adapter Roles

| Adapter Type | Current Adapter | Role |
|---|---|---|
| Repository | `AssetCatalogStore` | Processed asset catalog loading. |
| Graph | `Neo4jKnowledgeBaseGraphAdapter` | Relationship index and GraphRAG context. |
| Vector | `QdrantKnowledgeBaseVectorAdapter` | Future semantic retrieval index. |
| NoSQL | `InMemoryDocumentKnowledgeBaseAdapter` | Document-store baseline and future Mongo-style adapter. |
| Relational | `PostgresKnowledgeBaseRelationalAdapter` | Future runtime/audit/monitoring state. |

## Legacy Cleanup
The old wrapper packages `app/assets` and `app/knowledge_graph` were removed
after code and tests migrated to `app.knowledge_base`.
