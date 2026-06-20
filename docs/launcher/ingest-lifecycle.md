# Ingest Lifecycle - Pipeline Detallado con LangGraph

## Visión General

El pipeline de ingest usa **LangGraph StateGraph** con 14 nodos encadenados.
Cada nodo recibe y retorna un `IngestionGraphState` (TypedDict compartido).

```
scan_and_parse → analyze_semantics → build_extraction_instructions
    → extract_and_validate → [retry loop] → classify_asset_types
    → resolve_aliases_and_similarity → hydrate_asset_payloads
    → normalize_asset_relationships → generate_canonical_assets
    → persist_catalog → stage_asset_set_yaml
    → prepare_human_review_actions → persist_knowledge → write_audit
```

---

## Fase 1: Ingesta del Corpus

### Nodo 1: `scan_and_parse`

```
┌─────────────────────────────────────────────────────────────┐
│  INPUT:  raw_path (directorio con documentos)               │
│  OUTPUT: list[CorpusDocument]                               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. Escaneo recursivo del directorio                        │
│     └─→ Archivos soportados:                                │
│         .csv, .pdf, .png, .jpg, .docx, .txt, .md,          │
│         .json, .html, .yaml, .bpmn                          │
│                                                             │
│  2. Para cada archivo:                                      │
│     ├─→ Texto (.txt, .md, .json, .yaml):                   │
│     │   Lee como UTF-8, retorna CorpusDocument(path, text)  │
│     │                                                        │
│     ├─→ Imágenes (.png, .jpg):                              │
│     │   Base64-encode como data URL                         │
│     │   Retorna CorpusDocument(path, text="", data_url)     │
│     │                                                        │
│     ├─→ PDF (.pdf):                                         │
│     │   Intenta pdftotext (extracción de texto)             │
│     │   Fallback: pdftoppm (renderiza a imagen)             │
│     │                                                        │
│     └─→ DOCX (.docx):                                      │
│         ZIP-extract + XML-strip                             │
│                                                             │
│  3. Retorna lista de CorpusDocument objects                 │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Fase 2: Análisis Semántico

### Nodo 2: `analyze_semantics`

```
┌─────────────────────────────────────────────────────────────┐
│  INPUT:  list[CorpusDocument]                               │
│  OUTPUT: SemanticAnalysisResult                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Para cada documento, clasifica la INTENCIÓN:               │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  IntentClass (keyword heuristics):                    │   │
│  │                                                        │   │
│  │  qa              → "como", "que es", "por que"        │   │
│  │  guided_use_case → "paso 1", "primero", "despues"     │   │
│  │  process_exec    → "ejecutar", "procesar", "workflow" │   │
│  │  approval        → "aprobar", "revisar", "validar"    │   │
│  │  human_escalation→ "escalar", "supervisor", "manual"  │   │
│  │  document_search → "politica", "manual", "guia"       │   │
│  │  unknown         → fallback                            │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                             │
│  También extrae:                                            │
│  ├─→ knowledge_types (entity, process, business_rule, etc.) │
│  ├─→ processes (nombres de procesos encontrados)            │
│  ├─→ systems (sistemas mencionados)                         │
│  ├─→ confidence (0.0 - 1.0)                                │
│  └─→ needs_human_review (bool)                             │
│                                                             │
│  Resultado: lista de SemanticChunkClassification            │
│                                                             │
│  Opcional: LLMSemanticAnalyzerProvider (más preciso)        │
│  Envía cada chunk al LLM con prompt de clasificación        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Fase 3: Instrucciones de Extracción

### Nodo 3: `build_extraction_instructions`

```
┌─────────────────────────────────────────────────────────────┐
│  INPUT:  list[CorpusDocument], extraction_instruction_mode  │
│  OUTPUT: ExtractionInstructionSet + context string           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  6 Agentes con responsabilidades específicas:               │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  CorpusReaderAgent                                    │   │
│  │  "Read and summarize the corpus content"              │   │
│  │                                                        │   │
│  │  FlowDesignerAgent                                    │   │
│  │  "Propose candidate banking flows ONLY when the       │   │
│  │   corpus supports an end-to-end business process"     │   │
│  │                                                        │   │
│  │  TaskDecomposerAgent                                  │   │
│  │  "Decompose flows into user tasks with actions"       │   │
│  │                                                        │   │
│  │  ActionExtractorAgent                                 │   │
│  │  "Extract frontend/backend actions and tools"         │   │
│  │                                                        │   │
│  │  ConceptAgent                                         │   │
│  │  "Identify domain concepts, entities, synonyms"       │   │
│  │                                                        │   │
│  │  ValidatorAgent                                       │   │
│  │  "Validate extraction completeness and consistency"   │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                             │
│  Se renderizan como prompt context para el LLM              │
│                                                             │
│  ⚡ RETRY TARGET: si extract_and_validate falla,            │
│     el grafo regresa aquí para reintentar                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Fase 4: Extracción LLM + Validación

### Nodo 4: `extract_and_validate`

```
┌─────────────────────────────────────────────────────────────┐
│  INPUT:  documents, semantic_analysis, instructions         │
│  OUTPUT: extraction_result {flows, user_tasks, tools, ...}  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. PREPARACIÓN DEL PROMPT                                  │
│     └─→ Ensambla:                                           │
│         ├─→ System prompt (reglas de extracción)            │
│         ├─→ Schema prompt (JSON contract de assets)         │
│         ├─→ Extraction instructions (de los 6 agentes)      │
│         ├─→ Semantic analysis context (clasificación)       │
│         └─→ Corpus documents (texto + imágenes)             │
│                                                             │
│  2. ENVÍO AL LLM (OpenAI-compatible)                       │
│     ├─→ Si >12 docs o >20K chars:                          │
│     │   Batch con ThreadPoolExecutor (max 8 workers)        │
│     ├─→ Cada batch: llm_client.complete_json(prompt)        │
│     └─→ Retorna JSON structure                              │
│                                                             │
│  3. NORMALIZACIÓN Y VALIDACIÓN                              │
│     ├─→ Flows:                                              │
│     │   ├─→ Requiere: flow_id, flow_name, business_event,  │
│     │   │   explanation, >= 2 user_task_refs                │
│     │   ├─→ Clasificación estructural:                      │
│     │   │   ├─→ Rechaza si < 2 tasks (es user_task)        │
│     │   │   └─→ Rechaza si contexto = acción simple         │
│     │   └─→ Normaliza IDs (slug)                            │
│     │                                                        │
│     ├─→ User Tasks:                                         │
│     │   ├─→ Requiere: user_task_id, task, type              │
│     │   ├─→ Valida lifecycle_state                           │
│     │   └─→ Normaliza tools y actions                       │
│     │                                                        │
│     ├─→ Tools:                                              │
│     │   ├─→ Requiere: tool_id, tool_type, operation,        │
│     │   │   resource                                         │
│     │   └─→ Valida tool_type (frontend/backend/llm)         │
│     │                                                        │
│     └─→ Tool Registry:                                      │
│         └─→ Derivado de user task tools                     │
│                                                             │
│  4. REINTENTO (si falla)                                    │
│     └─→ _route_after_extract:                               │
│         ├─→ "write" si éxito → siguiente nodo               │
│         ├─→ "retry" si attempts <= max_retries              │
│         └─→ "fail" si agotó reintentos                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Fase 5: Clasificación y Normalización

### Nodo 5: `classify_asset_types`

```
┌─────────────────────────────────────────────────────────────┐
│  INPUT:  extraction_result, semantic_analysis               │
│  OUTPUT: asset_analysis.asset_types                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Clasifica candidatos en 18 tipos de assets:                │
│                                                             │
│  CONTENIDO:        CONTENEDOR:      CONOCIMIENTO:          │
│  ├─→ flow          ├─→ domain       ├─→ entity              │
│  ├─→ user_task     ├─→ module       ├─→ business_rule       │
│  ├─→ process       ├─→ menu         ├─→ ruleset             │
│  ├─→ plan          ├─→ form         ├─→ concept             │
│  ├─→ qa            ├─→ form_version ├─→ causality           │
│  └─→ tool          └─→ asset_set    └─→ document            │
│                                         └─→ configuration   │
│                                                             │
│  Para cada tipo cuenta:                                     │
│  ├─→ candidate_count (cuántos del LLM)                      │
│  ├─→ status ( draft | needs_review )                        │
│  └─→ payload_fields (campos esperados)                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Nodo 6: `resolve_aliases_and_similarity`

```
┌─────────────────────────────────────────────────────────────┐
│  INPUT:  extraction_result, asset_analysis                  │
│  OUTPUT: asset_analysis.aliases                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  RESOLUCIÓN DE ALIAS Y SINÓNIMOS:                           │
│                                                             │
│  1. Alias de Flows:                                         │
│     ├─→ flow_name → alias                                   │
│     ├─→ purpose → alias                                     │
│     ├─→ intent → alias                                      │
│     └─→ utterances (frases del usuario) → alias             │
│                                                             │
│  2. Alias de Concepts/Entities:                             │
│     ├─→ concept_name → alias                                │
│     ├─→ concept_aliases[concept] → lista de aliases         │
│     └─→ Ejemplo:                                           │
│         "prestamo" → ["credito", "loan", "financiamiento"]  │
│                                                             │
│  3. Alias de Tools:                                         │
│     ├─→ tool.label → alias                                  │
│     ├─→ tool.tool_id → alias                                │
│     └─→ tool.operation → alias                              │
│                                                             │
│  4. Deduplicación:                                          │
│     └─→ _dedupe_texts() elimina duplicados                  │
│                                                             │
│  ConceptVocabulary (vocabulary.py):                         │
│  ├─→ Carga catálogo de sinónimos:                           │
│  │   config/knowledge_base/concept_aliases.yaml             │
│  ├─→ normalize_term(term):                                  │
│  │   ├─→ Strip accents, lowercase, remove non-alphanum      │
│  │   ├─→ Map through alias index → canonical form            │
│  │   └─→ Retorna NormalizedTerm(raw, canonical, aliases)    │
│  ├─→ aliases_for(canonical): lista completa de aliases      │
│  └─→ expand_search_terms(terms): expande con aliases        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Nodo 7: `hydrate_asset_payloads`

```
┌─────────────────────────────────────────────────────────────┐
│  INPUT:  extraction_result, asset_analysis                  │
│  OUTPUT: asset_analysis.payloads                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Mapea cada tipo de asset a sus campos esperados:           │
│                                                             │
│  flow:        [flow_id, flow_name, purpose, intent,         │
│                business_event, inputs, outputs,              │
│                user_task_refs, explanation]                  │
│  user_task:   [user_task_id, task, type, description,       │
│                lifecycle_state, actions, tools]              │
│  tool:        [tool_id, tool_type, operation, resource,     │
│                label, description]                           │
│  entity:      [entity_id, entity_name, description,         │
│                attributes, relations]                        │
│  business_rule: [rule_id, rule_name, conditions,            │
│                  consequences, when_clause, then_clause]     │
│  ... (18 tipos en total)                                    │
│                                                             │
│  Configurable via YAML:                                     │
│  config/ingestion/payload_composition.yaml                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Nodo 8: `normalize_asset_relationships`

```
┌─────────────────────────────────────────────────────────────┐
│  INPUT:  extraction_result, asset_analysis                  │
│  OUTPUT: asset_analysis.relationships                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Construye relaciones cross-asset:                           │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  RELATION TYPE          SOURCE → TARGET               │   │
│  │                                                        │   │
│  │  belongs_to_domain      module → domain               │   │
│  │  belongs_to_module      menu, form → module           │   │
│  │  version_of             form_version → form           │   │
│  │  groups_*               asset_set → (cualquier tipo)  │   │
│  │  decomposes_to_user_task flow → user_task             │   │
│  │  invokes_tool           user_task → tool              │   │
│  │  uses_concept           flow → concept                │   │
│  │  uses_entity            flow, rule → entity           │   │
│  │  applies_to_flow        business_rule → flow          │   │
│  │  applies_to_process     business_rule → process       │   │
│  │  implements_flow        process → flow                │   │
│  │  governed_by_rule       flow, process → business_rule │   │
│  │  has_cause              causality → entity/rule       │   │
│  │  has_effect             causality → entity/rule       │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                             │
│  NORMALIZACIÓN DE RELACIONES:                               │
│  (RelationNormalizationService)                             │
│                                                             │
│  1. Alias lookup:                                           │
│     └─→ registry.resolve(raw_type) → canonical_type         │
│                                                             │
│  2. Fallback vector similarity (threshold 0.82):            │
│     └─→ compara embedding del tipo raw vs canonical         │
│                                                             │
│  3. Fallback passthrough (raw type)                         │
│                                                             │
│  4. Validación de compatibilidad:                           │
│     └─→ source_type + target_type son válidos?              │
│                                                             │
│  5. Metadata por relación:                                  │
│     ├─→ raw_relation_type                                   │
│     ├─→ canonical_relation_type                             │
│     ├─→ relation_family (structural/semantic/causality)     │
│     ├─→ normalization_strategy (alias/vector/passthrough)   │
│     └─→ review_required (bool)                              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Fase 6: Generación de Assets Canónicos

### Nodo 9: `generate_canonical_assets`

```
┌─────────────────────────────────────────────────────────────┐
│  INPUT:  extraction_result, documents, asset_analysis       │
│  OUTPUT: canonical_assets [EnterpriseAsset, ...]            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  CanonicalAssetPipeline.run() tiene 4 fases:                │
│                                                             │
│  FASE A: extract_candidates()                               │
│  ├─→ _document_candidates (texto raw del corpus)            │
│  ├─→ _container_config_candidates (domain/module/menu/form) │
│  ├─→ _entity_candidates:                                    │
│  │   ├─→ Concepts del LLM → ConceptVocabulary.normalize()   │
│  │   ├─→ CSV glossary rows                                  │
│  │   ├─→ Markdown "entities" sections                       │
│  │   └─→ Causality cause/effect endpoints                   │
│  ├─→ _tool_candidates (del tool_registry)                   │
│  ├─→ _user_task_candidates (del array user_tasks)           │
│  ├─→ _flow_candidates (del array flows)                     │
│  ├─→ _rule_candidates (business_rules)                      │
│  ├─→ _process_candidates (processes)                        │
│  ├─→ _plan_candidates (plans)                               │
│  ├─→ _qa_candidates (qa items)                              │
│  └─→ _causality_candidates (cause/effect pairs)             │
│                                                             │
│  FASE B: enrich_relations()                                 │
│  ├─→ RelationPatternCatalog: patrones de texto → relations   │
│  ├─→ Entity linking: escanea texto, resuelve entidades      │
│  └─→ adds uses_entity relations                             │
│                                                             │
│  FASE C: _group_transaction_assets()                        │
│  ├─→ Agrupa por transaction_id                              │
│  ├─→ Crea ruleset candidates                               │
│  └─→ Crea asset_set candidates                             │
│                                                             │
│  FASE D: canonicalizer.normalize()                          │
│  ├─→ Dedup por (asset_type, normalized_name)                │
│  ├─→ Merge aliases de duplicados                            │
│  ├─→ Sanitize aliases (remueve reserved words)              │
│  ├─→ Fuzzy match contra assets existentes (0.93 threshold)  │
│  └─→ Produce EnterpriseAsset objects                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Fase 7: Persistencia

### Nodo 10: `persist_catalog`

```
┌─────────────────────────────────────────────────────────────┐
│  INPUT:  canonical_assets, catalog_store, registry          │
│  OUTPUT: catalog_assets_persisted count                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Para cada EnterpriseAsset:                                 │
│  └─→ catalog_store.upsert_asset(asset, registry)            │
│      ├─→ INSERT/UPDATE en tabla assets                      │
│      ├─→ INSERT en tabla relationships                      │
│      └─→ Assets status: DRAFT                               │
│                                                             │
│  ⚡ Solo si config.apply = True                             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Nodo 11: `stage_asset_set_yaml`

```
┌─────────────────────────────────────────────────────────────┐
│  INPUT:  canonical_assets, staging_directory                │
│  OUTPUT: staged_asset_sets [StagedAssetSet, ...]            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Para cada tipo de asset:                                   │
│  ├─→ Crea directorio: {run_root}/{asset_type}-set/assets/   │
│  ├─→ Escribe cada asset como YAML:                          │
│  │   asset_id, asset_type, name, version,                   │
│  │   description, tags, relations, payload                  │
│  └─→ Crea manifest: asset-set.yaml                          │
│      apiVersion: catalog.unify/v1                           │
│      kind: AssetSet                                         │
│      metadata: {id, name, version, domain, module}          │
│      spec: {assetType, assets[]}                            │
│                                                             │
│  Output:                                                    │
│  app/assets/staging/ingest-runs/{timestamp}/                │
│  ├─→ flow-set/asset-set.yaml + assets/*.yaml               │
│  ├─→ user_task-set/asset-set.yaml + assets/*.yaml          │
│  ├─→ entity-set/asset-set.yaml + assets/*.yaml             │
│  └─→ ... (cada tipo)                                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Nodo 12: `prepare_human_review_actions`

```
┌─────────────────────────────────────────────────────────────┐
│  INPUT:  asset_analysis                                     │
│  OUTPUT: asset_analysis.human_review_actions                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Genera acciones de review para:                            │
│  ├─→ approve_asset_candidates (por cada tipo con candidatos)│
│  ├─→ confirm_missing_asset_type (tipos solo de schema)      │
│  ├─→ approve_aliases (si hay aliases)                       │
│  ├─→ approve_relationships (si hay relaciones)              │
│  └─→ approve_staged_asset_sets (si hay sets staging)        │
│                                                             │
│  Cada acción tiene:                                         │
│  ├─→ action_type                                            │
│  ├─→ asset_type                                             │
│  ├─→ candidate_count                                        │
│  └─→ status (pending)                                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Nodo 13: `persist_knowledge`

```
┌─────────────────────────────────────────────────────────────┐
│  INPUT:  extraction_result, canonical_assets,               │
│          staged_asset_sets, knowledge_base_service          │
│  OUTPUT: knowledge_base_error                                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  DOS PATHS DE PERSISTENCIA:                                 │
│                                                             │
│  PATH 1: Catalog AssetSets                                  │
│  ├─→ Si apply=True AND project_knowledge_bases=True         │
│  ├─→ Para cada StagedAssetSet:                              │
│  │   └─→ AssetSetDeploymentService.load(manifest)           │
│  │       ├─→ Crea AssetSet en catalog                       │
│  │       ├─→ Agrega members                                 │
│  │       └─→ Status: draft                                  │
│  └─→ Deploy a stores configurados                           │
│                                                             │
│  PATH 2: Knowledge Base (Graph + Vector + Document)         │
│  ├─→ Si kb_service exists AND apply=True                    │
│  │   AND project_knowledge_bases=True                       │
│  ├─→ Convierte extraction_result a KnowledgeRecords         │
│  └─→ kb_service.ingest(records, clear=clean)                │
│      ├─→ Graph (Neo4j):                                     │
│      │   ├─→ Flow nodes + relationships                     │
│      │   ├─→ UserTask nodes + tool bindings                 │
│      │   ├─→ Entity nodes + aliases                         │
│      │   └─→ BusinessRule nodes + conditions                │
│      │                                                       │
│      ├─→ Vector (Qdrant):                                   │
│      │   ├─→ Embeddings de flows (nombre + propósito)       │
│      │   ├─→ Embeddings de QA (pregunta + respuesta)        │
│      │   └─→ Embeddings de documentos fuente                │
│      │                                                       │
│      └─→ Document (SQLite):                                 │
│          ├─→ Texto completo de flows                        │
│          ├─→ Texto de business rules                        │
│          └─→ Texto de documentos fuente                     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Nodo 14: `write_audit`

```
┌─────────────────────────────────────────────────────────────┐
│  INPUT:  todo el state acumulado                            │
│  OUTPUT: audit_path, final_result                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Escribe JSON de auditoría completo:                        │
│  {                                                          │
│    started_at, finished_at, mode,                           │
│    extraction_instruction_mode,                             │
│    semantic_analysis,                                       │
│    extraction_instructions,                                 │
│    raw_path,                                                │
│    source_files: [{path, sha256}],                          │
│    outputs: {                                               │
│      flows: N,                                              │
│      user_tasks: N,                                         │
│      tools: N,                                              │
│      canonical_assets: N,                                   │
│      staged_asset_sets: N,                                  │
│      catalog_assets_persisted: N,                           │
│      knowledge_base_error: ""                               │
│    },                                                       │
│    steps: [cada nodo ejecutado con timestamps]              │
│  }                                                          │
│                                                             │
│  Si human_review requerido:                                 │
│  └─→ Escribe review artifact para el launcher               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Ciclo de Vida del Asset (post-ingest)

```
         INGEST                    HUMAN REVIEW              DEPLOY
    ┌──────────────┐          ┌──────────────────┐     ┌──────────────┐
    │   draft      │  ──────→ │ ready_for_review │ ──→ │   validated  │
    │              │          │                  │     │              │
    │ En todos los │          │ Editor en        │     │ Auto-valida  │
    │ stores:      │          │ launcher:        │     │ schema +     │
    │ catalog      │          │ payload, relations│     │ relations    │
    │ graph        │          │ status change    │     │              │
    │ vector       │          │                  │     │              │
    │ document     │          │                  │     │              │
    └──────────────┘          └──────────────────┘     └──────┬───────┘
                                                              │
                                                              ↓
                                                      ┌──────────────┐
                                                      │   active     │
                                                      │              │
                                                      │ Proyecciones │
                                                      │ habilitadas: │
                                                      │ graph → query│
                                                      │ vector → search│
                                                      │ document → text│
                                                      └──────────────┘
```

### Domain Events en cada transición:

```python
# Ingest crea el asset
emit_asset_status_change(asset_id, "flow", "draft", "draft")

# Humano cambia a ready_for_review
emit_asset_status_change(asset_id, "flow", "draft", "ready_for_review")

# Validación automática
emit_asset_status_change(asset_id, "flow", "ready_for_review", "validated")

# Deploy activa
emit_asset_status_change(asset_id, "flow", "validated", "active")

# Edición post-deploy crea nueva versión
emit_asset_status_change(asset_id, "flow", "active", "draft")  # nueva versión
```
