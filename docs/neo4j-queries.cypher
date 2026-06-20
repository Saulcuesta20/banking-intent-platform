// ============================================
// Banking Intent Platform - Neo4j Filter Queries
// ============================================
// Copia y pega estas queries en http://localhost:7474/browser/
// ============================================


// ============================================
// 1. RESUMEN POR KB (equivale a kb stats)
// ============================================
MATCH (kb:KnowledgeBase)
OPTIONAL MATCH (a:Asset)-[:OWNED_BY]->(kb)
OPTIONAL MATCH (a)-[:STORED_IN]->(eng:Engine)
RETURN
  kb.name AS knowledge_base,
  count(DISTINCT a) AS total_assets,
  collect(DISTINCT eng.name) AS engines
ORDER BY total_assets DESC


// ============================================
// 2. FILTRAR POR KB
// ============================================

// business_model_kb
MATCH (a:Asset)-[:OWNED_BY]->(kb:KnowledgeBase {name: 'business_model_kb'})
RETURN a.asset_id AS id, a.name AS name, a.asset_type AS type, a.structural_layer AS layer
ORDER BY a.structural_layer, a.name

// process_kb
MATCH (a:Asset)-[:OWNED_BY]->(kb:KnowledgeBase {name: 'process_kb'})
RETURN a.asset_id AS id, a.name AS name, a.asset_type AS type
ORDER BY a.name

// rules_kb
MATCH (a:Asset)-[:OWNED_BY]->(kb:KnowledgeBase {name: 'rules_kb'})
RETURN a.asset_id AS id, a.name AS name, a.asset_type AS type
ORDER BY a.name

// config_kb
MATCH (a:Asset)-[:OWNED_BY]->(kb:KnowledgeBase {name: 'config_kb'})
RETURN a.asset_id AS id, a.name AS name, a.asset_type AS type
ORDER BY a.name


// ============================================
// 3. FILTRAR POR STRUCTURAL LAYER
// ============================================

// Todas las entidades por layer
MATCH (sl:StructuralLayer)-[:CLASSIFIES]->(a:Asset)
RETURN sl.name AS layer, a.asset_id AS id, a.name AS name, a.asset_type AS type
ORDER BY sl.name, a.name

// Solo party (personas/entidades)
MATCH (sl:StructuralLayer {name: 'party'})-[:CLASSIFIES]->(a:Asset)
RETURN a

// Solo channel (plataformas)
MATCH (sl:StructuralLayer {name: 'channel'})-[:CLASSIFIES]->(a:Asset)
RETURN a

// Solo business_resource (recursos del negocio)
MATCH (sl:StructuralLayer {name: 'business_resource'})-[:CLASSIFIES]->(a:Asset)
RETURN a

// Solo capability (funciones)
MATCH (sl:StructuralLayer {name: 'capability'})-[:CLASSIFIES]->(a:Asset)
RETURN a


// ============================================
// 4. FILTRAR POR ENGINE
// ============================================

// Assets en Neo4j (graph)
MATCH (a:Asset)-[:STORED_IN]->(eng:Engine {name: 'neo4j'})
RETURN a.asset_id AS id, a.name AS name, a.asset_type AS type, a.primary_kb AS kb
ORDER BY a.primary_kb, a.name

// Assets en Qdrant (vector)
MATCH (a:Asset)-[:STORED_IN]->(eng:Engine {name: 'qdrant'})
RETURN a.asset_id AS id, a.name AS name, a.asset_type AS type, a.primary_kb AS kb
ORDER BY a.primary_kb, a.name

// Assets en SQLite (document)
MATCH (a:Asset)-[:STORED_IN]->(eng:Engine {name: 'sqlite'})
RETURN a.asset_id AS id, a.name AS name, a.asset_type AS type, a.primary_kb AS kb
ORDER BY a.primary_kb, a.name


// ============================================
// 5. FILTROS COMBINADOS
// ============================================

// Entidades party en business_model_kb
MATCH (a:Asset:Entity)-[:OWNED_BY]->(kb:KnowledgeBase {name: 'business_model_kb'})
WHERE a.structural_layer = 'party'
RETURN a

// Entidades channel en business_model_kb
MATCH (a:Asset:Entity)-[:OWNED_BY]->(kb:KnowledgeBase {name: 'business_model_kb'})
WHERE a.structural_layer = 'channel'
RETURN a

// Entidades business_resource en business_model_kb
MATCH (a:Asset:Entity)-[:OWNED_BY]->(kb:KnowledgeBase {name: 'business_model_kb'})
WHERE a.structural_layer = 'business_resource'
RETURN a

// Tools en business_model_kb
MATCH (a:Asset:ToolAsset)-[:OWNED_BY]->(kb:KnowledgeBase {name: 'business_model_kb'})
RETURN a

// UserTasks en business_model_kb
MATCH (a:Asset:UserTaskAsset)-[:OWNED_BY]->(kb:KnowledgeBase {name: 'business_model_kb'})
RETURN a

// Flows en process_kb
MATCH (a:Asset:FlowAsset)-[:OWNED_BY]->(kb:KnowledgeBase {name: 'process_kb'})
RETURN a

// Business rules en rules_kb
MATCH (a:Asset:BusinessRule)-[:OWNED_BY]->(kb:KnowledgeBase {name: 'rules_kb'})
RETURN a


// ============================================
// 6. FLUJO DE RELACIONES (flow -> entity)
// ============================================

// Qué flows usan qué entidades
MATCH (f:FlowAsset)-[:USES_ENTITY]->(e:Entity)
RETURN f.name AS flow, e.name AS entity, e.structural_layer AS layer
ORDER BY f.name, e.name

// Entidades usadas por un flow específico
MATCH (f:FlowAsset {asset_id: 'flow.savings.account.open'})-[:USES_ENTITY]->(e:Entity)
RETURN f.name AS flow, e.name AS entity, e.structural_layer AS layer

// Qué entidades usa cada flow, agrupado por layer
MATCH (f:FlowAsset)-[:USES_ENTITY]->(e:Entity)
RETURN e.structural_layer AS layer, count(DISTINCT f) AS flows, collect(DISTINCT e.name) AS entities
ORDER BY layer


// ============================================
// 7. RESUMEN DE DIMENSIONES
// ============================================

// Conteo por cada dimensión
MATCH (a:Asset)
RETURN
  count(CASE WHEN a:Entity THEN 1 END) AS entities,
  count(CASE WHEN a:FlowAsset THEN 1 END) AS flows,
  count(CASE WHEN a:UserTaskAsset THEN 1 END) AS user_tasks,
  count(CASE WHEN a:ToolAsset THEN 1 END) AS tools,
  count(CASE WHEN a:BusinessRule THEN 1 END) AS business_rules,
  count(*) AS total


// ============================================
// 8. TABLA COMPLETA (equivale a kb stats table)
// ============================================
MATCH (a:Asset)
OPTIONAL MATCH (a)-[:OWNED_BY]->(kb:KnowledgeBase)
OPTIONAL MATCH (a)-[:STORED_IN]->(eng:Engine)
OPTIONAL MATCH (sl:StructuralLayer)-[:CLASSIFIES]->(a)
RETURN
  kb.name AS kb,
  sl.name AS layer,
  a.asset_type AS type,
  a.name AS name,
  collect(DISTINCT eng.name) AS engines
ORDER BY kb.name, sl.name, a.asset_type, a.name
