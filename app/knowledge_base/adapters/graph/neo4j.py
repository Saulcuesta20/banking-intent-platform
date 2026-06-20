from __future__ import annotations

import json
import re
from typing import Any

from app.knowledge_base.ports import GraphKnowledgeBaseAdapter
from app.knowledge_base.models import EnterpriseAsset
from app.models import KnowledgeRecord, Task, UserTask
from app.tools.models import ToolDefinition


def _optional_import(module_name: str, friendly_name: str | None = None):
    try:
        return __import__(module_name)
    except ImportError as exc:
        raise RuntimeError(
            f"Optional dependency '{friendly_name or module_name}' is required for this provider."
        ) from exc


class Neo4jKnowledgeBaseGraphAdapter(GraphKnowledgeBaseAdapter):
    """Graph adapter that indexes and searches approved knowledge in Neo4j."""

    GRAPH_CONTEXT_QUERY = """
        MATCH (f:Flow)
        OPTIONAL MATCH (launcher_asset:Asset:FlowAsset {asset_id: 'flow.' + f.flow_id})
        OPTIONAL MATCH (f)-[:EXEMPLIFIES]->(u:Utterance)
        OPTIONAL MATCH (f)-[:RELATES_TO]->(c:Concept)
        OPTIONAL MATCH (c)-[:HAS_SYNONYM]->(s:Synonym)
        OPTIONAL MATCH (f)-[task_rel:HAS_USER_TASK]->(t:UserTask)
        OPTIONAL MATCH (t)-[:USES_TOOL]->(tool:Tool)
        RETURN
          f.flow_id AS flow_id,
          f.flow_name AS flow_name,
          f.intent AS intent,
          f.business_event AS business_event,
          f.confidence AS confidence,
          f.explanation AS explanation,
          f.plan AS plan,
          f.capabilities AS capabilities,
          f.source AS source,
          coalesce(launcher_asset.launcher_enabled, false) AS launcher_enabled,
          collect(DISTINCT u.text) AS utterances,
          collect(DISTINCT c.name) AS concepts,
          collect(DISTINCT s.term) AS concept_aliases,
          collect(DISTINCT {task: t.task, type: t.type, order_index: task_rel.sequence}) AS user_tasks,
          collect(DISTINCT tool.tool_id) AS tools
        ORDER BY flow_id
        """

    FILTERED_GRAPH_CONTEXT_QUERY = """
        MATCH (f:Flow)
        OPTIONAL MATCH (launcher_asset:Asset:FlowAsset {asset_id: 'flow.' + f.flow_id})
        OPTIONAL MATCH (f)-[:EXEMPLIFIES]->(u_match:Utterance)
        OPTIONAL MATCH (f)-[:RELATES_TO]->(c_match:Concept)
        OPTIONAL MATCH (c_match)-[:HAS_SYNONYM]->(s_match:Synonym)
        WITH f, launcher_asset,
             collect(DISTINCT u_match.text) AS all_utterances,
             collect(DISTINCT c_match.name) AS all_concepts,
             collect(DISTINCT s_match.term) AS all_concept_aliases,
             toLower(
               coalesce(f.flow_id, '') + ' ' +
               coalesce(f.flow_name, '') + ' ' +
               coalesce(f.intent, '') + ' ' +
               coalesce(f.business_event, '') + ' ' +
               coalesce(f.explanation, '') + ' ' +
               reduce(text = '', value IN collect(DISTINCT u_match.text) | text + ' ' + coalesce(value, '')) + ' ' +
               reduce(text = '', value IN collect(DISTINCT c_match.name) | text + ' ' + coalesce(value, '')) + ' ' +
               reduce(text = '', value IN collect(DISTINCT s_match.term) | text + ' ' + coalesce(value, ''))
             ) AS haystack
        WITH f, launcher_asset, all_utterances, all_concepts, all_concept_aliases,
             [token IN $tokens WHERE haystack CONTAINS token] AS matched_tokens
        WHERE size(matched_tokens) > 0
        OPTIONAL MATCH (f)-[task_rel:HAS_USER_TASK]->(t:UserTask)
        OPTIONAL MATCH (t)-[:USES_TOOL]->(tool:Tool)
        RETURN
          f.flow_id AS flow_id,
          f.flow_name AS flow_name,
          f.intent AS intent,
          f.business_event AS business_event,
          f.confidence AS confidence,
          f.explanation AS explanation,
          f.plan AS plan,
          f.capabilities AS capabilities,
          f.source AS source,
          coalesce(launcher_asset.launcher_enabled, false) AS launcher_enabled,
          all_utterances AS utterances,
          all_concepts AS concepts,
          all_concept_aliases AS concept_aliases,
          collect(DISTINCT {task: t.task, type: t.type, order_index: task_rel.sequence}) AS user_tasks,
          collect(DISTINCT tool.tool_id) AS tools,
          matched_tokens AS matched_tokens,
          size(matched_tokens) AS match_score
        ORDER BY match_score DESC, flow_id
        LIMIT $limit
        """

    def __init__(
        self,
        neo4j_uri: str,
        neo4j_user: str,
        neo4j_password: str,
        limit: int = 50,
    ):
        neo4j = _optional_import("neo4j")
        self.driver = neo4j.GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        self.neo4j_uri = neo4j_uri
        self.limit = limit

    def search(self, search_terms: list[str]) -> list[KnowledgeRecord]:
        tokens = self._search_tokens(search_terms)
        graph_rows = self._query_graph_context(tokens)
        if not graph_rows:
            broad_rows = self._query_all_graph_context()
            return [
                self._record_from_row(row).model_copy(
                    update={
                        "metadata": {
                            **self._record_from_row(row).metadata,
                            "knowledge_provider": "neo4j_broad_context",
                            "graph_query_summary": self._query_summary(
                                query=self.GRAPH_CONTEXT_QUERY,
                                row_count=len(broad_rows),
                                tokens=tokens,
                                search_mode="broad_graph_context",
                            ),
                            "graph_rows_preview": self._rows_preview(broad_rows),
                            "graph_context": self._context_text(row),
                        }
                    }
                )
                for row in broad_rows[: self.limit]
            ]

        candidates = []
        for row in graph_rows:
            record = self._record_from_row(row)
            candidates.append(
                record.model_copy(
                    update={
                        "metadata": {
                            **record.metadata,
                            "knowledge_provider": "neo4j",
                            "graph_query_summary": self._query_summary(
                                query=self.FILTERED_GRAPH_CONTEXT_QUERY,
                                row_count=len(graph_rows),
                                tokens=tokens,
                                search_mode="filtered_graph_context",
                            ),
                            "graph_rows_preview": self._rows_preview(graph_rows),
                            "graph_context": self._context_text(row),
                        }
                    }
                )
            )
        return candidates[: self.limit]

    @staticmethod
    def _search_tokens(search_terms: list[str]) -> list[str]:
        values: list[str] = []
        seen: set[str] = set()
        for term in search_terms:
            normalized = " ".join(str(term).casefold().split())
            candidates = [normalized, *re.findall(r"[a-z0-9áéíóúñ]+", normalized)]
            for candidate in candidates:
                if len(candidate) <= 2 or candidate in seen:
                    continue
                seen.add(candidate)
                values.append(candidate)
        return values

    def list_all_records(self) -> list[KnowledgeRecord]:
        return [self._record_from_row(row) for row in self._query_all_graph_context()]

    def close(self) -> None:
        self.driver.close()

    def initialize(self) -> None:
        with self.driver.session() as session:
            session.execute_write(self._create_constraints)
            session.execute_write(self._create_dimension_nodes)

    def clear(self) -> None:
        with self.driver.session() as session:
            session.execute_write(self._clear_graph)

    def upsert_record(self, record: KnowledgeRecord) -> None:
        with self.driver.session() as session:
            session.execute_write(self._upsert_record, record)

    def upsert_asset(self, asset: EnterpriseAsset) -> None:
        if not self._should_project_asset(asset):
            return
        with self.driver.session() as session:
            session.execute_write(self._upsert_asset, asset)

    def get_asset(self, asset_id: str) -> EnterpriseAsset | None:
        with self.driver.session() as session:
            record = session.run(
                """
                MATCH (asset:Asset {asset_id: $asset_id})
                RETURN asset {
                  .asset_id, .asset_type, .name, .version, .status, .owner,
                  .description, .text, .tags, .source_refs, .payload_json
                } AS asset,
                [(asset)-[relation]->(target:Asset) WHERE relation.relation_type IS NOT NULL |
                  {
                    type: coalesce(relation.relation_type, toLower(type(relation))),
                    target_asset_id: target.asset_id,
                    metadata: relation.metadata
                  }
                ] AS relations
                """,
                {"asset_id": asset_id},
            ).single()
        return self._asset_from_row(dict(record)) if record else None

    def list_assets(
        self,
        asset_type: str | None = None,
        approved_only: bool = True,
    ) -> list[EnterpriseAsset]:
        clauses = []
        parameters: dict[str, Any] = {}
        if asset_type:
            clauses.append("asset.asset_type = $asset_type")
            parameters["asset_type"] = asset_type
        if approved_only:
            clauses.append("asset.status IN ['approved', 'validated', 'active']")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.driver.session() as session:
            rows = [
                dict(record)
                for record in session.run(
                    f"""
                    MATCH (asset:Asset)
                    {where}
                    RETURN asset {{
                      .asset_id, .asset_type, .name, .version, .status, .owner,
                      .description, .text, .tags, .source_refs, .payload_json
                    }} AS asset,
                    [(asset)-[relation]->(target:Asset) WHERE relation.relation_type IS NOT NULL |
                      {{
                        type: coalesce(relation.relation_type, toLower(type(relation))),
                        target_asset_id: target.asset_id,
                        metadata: relation.metadata
                      }}
                    ] AS relations
                    ORDER BY asset.asset_type, asset.asset_id
                    """,
                    parameters,
                )
            ]
        return [self._asset_from_row(row) for row in rows]

    @staticmethod
    def _create_constraints(tx: Any) -> None:
        tx.run("CREATE CONSTRAINT IF NOT EXISTS FOR (f:Flow) REQUIRE f.flow_id IS UNIQUE")
        tx.run("CREATE CONSTRAINT IF NOT EXISTS FOR (a:Action) REQUIRE a.action IS UNIQUE")
        tx.run("CREATE CONSTRAINT IF NOT EXISTS FOR (ua:UserAction) REQUIRE ua.action_id IS UNIQUE")
        tx.run("CREATE CONSTRAINT IF NOT EXISTS FOR (tool:Tool) REQUIRE tool.tool_id IS UNIQUE")
        tx.run("CREATE CONSTRAINT IF NOT EXISTS FOR (c:Concept) REQUIRE c.name IS UNIQUE")
        tx.run("CREATE CONSTRAINT IF NOT EXISTS FOR (s:Synonym) REQUIRE s.term IS UNIQUE")
        tx.run("CREATE CONSTRAINT IF NOT EXISTS FOR (t:UserTask) REQUIRE t.task IS UNIQUE")
        tx.run("CREATE CONSTRAINT IF NOT EXISTS FOR (u:Utterance) REQUIRE u.text IS UNIQUE")
        tx.run("CREATE CONSTRAINT IF NOT EXISTS FOR (a:Asset) REQUIRE a.asset_id IS UNIQUE")
        # Dimension node constraints
        tx.run("CREATE CONSTRAINT IF NOT EXISTS FOR (kb:KnowledgeBase) REQUIRE kb.name IS UNIQUE")
        tx.run("CREATE CONSTRAINT IF NOT EXISTS FOR (eng:Engine) REQUIRE eng.name IS UNIQUE")
        tx.run("CREATE CONSTRAINT IF NOT EXISTS FOR (sl:StructuralLayer) REQUIRE sl.name IS UNIQUE")
        # Indexes for dimension-based filtering
        tx.run("CREATE INDEX IF NOT EXISTS FOR (a:Asset) ON (a.primary_kb)")
        tx.run("CREATE INDEX IF NOT EXISTS FOR (a:Asset) ON (a.structural_layer)")
        tx.run("CREATE INDEX IF NOT EXISTS FOR (a:Asset) ON (a.asset_type)")
        tx.run("CREATE INDEX IF NOT EXISTS FOR (a:Asset) ON (a.engine)")
        tx.run("CREATE INDEX IF NOT EXISTS FOR (a:Asset) ON (a.status)")

    # Dimension node definitions
    KNOWLEDGE_BASES = [
        {"name": "business_model_kb", "description": "Business model entities, tools, user tasks, and semantic spaces"},
        {"name": "process_kb", "description": "Business processes, flows, and asset sets"},
        {"name": "rules_kb", "description": "Business rules and rulesets"},
        {"name": "planning_kb", "description": "Planning and roadmap assets"},
        {"name": "causality_kb", "description": "Cause-effect relationships"},
        {"name": "document_kb", "description": "Source documents and corpus chunks"},
        {"name": "qa_kb", "description": "Question and answer pairs"},
        {"name": "config_kb", "description": "Configuration, domains, modules, and forms"},
    ]

    ENGINES = [
        {"name": "neo4j", "kind": "graph", "description": "Graph relationships, flows, processes, tasks, tools, concepts"},
        {"name": "qdrant", "kind": "vector", "description": "Semantic/vector search for text evidence"},
        {"name": "sqlite", "kind": "document", "description": "Document storage for long manuals and corpus chunks"},
        {"name": "catalog", "kind": "repository", "description": "Unified Catalog of approved YAML/JSON assets"},
    ]

    STRUCTURAL_LAYERS = [
        {"name": "party", "description": "Personas o entidades externas/internas que participan"},
        {"name": "organization", "description": "Divisiones, direcciones, departamentos y estructura"},
        {"name": "capability", "description": "Funciones o centros de competencia"},
        {"name": "portfolio", "description": "Conjuntos estructurados de productos/servicios"},
        {"name": "offering", "description": "Producto o servicio individual comercializable"},
        {"name": "program", "description": "Iniciativas, campañas o planes coordinados"},
        {"name": "channel", "description": "Medios y plataformas por donde interactúa"},
        {"name": "transaction", "description": "Movimientos operativos o financieros"},
        {"name": "agreement", "description": "Contratos, políticas y consentimientos"},
        {"name": "event", "description": "Hitos, SLA y cambios de estado"},
        {"name": "metric", "description": "Indicadores y KPIs"},
        {"name": "workforce", "description": "Personas/puestos concretos dentro de la empresa"},
        {"name": "workforce_role", "description": "Roles o perfiles reutilizables"},
        {"name": "business_resource", "description": "Recursos del negocio: plataformas, sistemas, documentos"},
    ]

    @staticmethod
    def _create_dimension_nodes(tx: Any) -> None:
        """Create KnowledgeBase, Engine, and StructuralLayer dimension nodes."""
        for kb in Neo4jKnowledgeBaseGraphAdapter.KNOWLEDGE_BASES:
            tx.run(
                "MERGE (kb:KnowledgeBase {name: $name}) "
                "SET kb.description = $description, kb.kind = 'knowledge_base'",
                kb,
            )
        for eng in Neo4jKnowledgeBaseGraphAdapter.ENGINES:
            tx.run(
                "MERGE (eng:Engine {name: $name}) "
                "SET eng.kind = $kind, eng.description = $description, eng.dimension = 'engine'",
                eng,
            )
        for layer in Neo4jKnowledgeBaseGraphAdapter.STRUCTURAL_LAYERS:
            tx.run(
                "MERGE (sl:StructuralLayer {name: $name}) "
                "SET sl.description = $description, sl.dimension = 'structural_layer'",
                layer,
            )

    @staticmethod
    def _clear_graph(tx: Any) -> None:
        # Delete ALL nodes EXCEPT dimension nodes (KnowledgeBase, Engine, StructuralLayer)
        tx.run(
            "MATCH (n) WHERE NOT n:KnowledgeBase AND NOT n:Engine AND NOT n:StructuralLayer "
            "DETACH DELETE n"
        )

    @staticmethod
    def _upsert_record(tx: Any, record: KnowledgeRecord) -> None:
        tx.run(
            "MERGE (f:Flow {flow_id: $flow_id}) "
            "SET f.flow_name = $flow_name, f.source = $source, f.intent = $intent, "
            "f.business_event = $business_event, f.explanation = $explanation, f.confidence = $confidence, "
            "f.plan = $plan, f.capabilities = $capabilities",
            {
                "flow_id": record.flow_id,
                "flow_name": record.flow_name,
                "source": record.source,
                "intent": record.intent,
                "business_event": record.business_event,
                "explanation": record.explanation,
                "confidence": record.confidence,
                "plan": record.plan,
                "capabilities": record.capabilities,
            },
        )
        for action in record.capabilities:
            tx.run("MERGE (a:Action {action: $action}) SET a.type = coalesce(a.type, 'declared_action')", {"action": action})
            tx.run("MATCH (f:Flow {flow_id: $flow_id}), (a:Action {action: $action}) MERGE (f)-[:DECLARES_ACTION]->(a)", {"flow_id": record.flow_id, "action": action})
        for concept in record.concepts:
            tx.run("MERGE (c:Concept {name: $concept})", {"concept": concept})
            tx.run("MATCH (f:Flow {flow_id: $flow_id}), (c:Concept {name: $concept}) MERGE (f)-[:RELATES_TO]->(c)", {"flow_id": record.flow_id, "concept": concept})
            for alias in record.concept_aliases.get(concept, []):
                tx.run("MERGE (s:Synonym {term: $alias}) SET s.normalized = true", {"alias": alias})
                tx.run(
                    "MATCH (c:Concept {name: $concept}), (s:Synonym {term: $alias}) "
                    "MERGE (c)-[:HAS_SYNONYM]->(s) MERGE (s)-[:NORMALIZES_TO]->(c)",
                    {"concept": concept, "alias": alias},
                )
        for index, task in enumerate(record.user_tasks, start=1):
            tx.run("MERGE (t:UserTask {task: $task}) SET t.type = $type", {"task": task.task, "type": task.type})
            tx.run(
                "MATCH (f:Flow {flow_id: $flow_id}), (t:UserTask {task: $task}) "
                "MERGE (f)-[rel:HAS_USER_TASK]->(t) SET rel.sequence = $sequence",
                {"flow_id": record.flow_id, "task": task.task, "sequence": index},
            )
            for action in task.user_actions:
                Neo4jKnowledgeBaseGraphAdapter._upsert_task_user_action(tx, record.flow_id, task.task, action.to_dict())
            for tool in task.tools:
                Neo4jKnowledgeBaseGraphAdapter._upsert_task_tool(tx, record.flow_id, task.task, tool.to_dict())
        for utterance in record.utterances[:20]:
            tx.run("MERGE (u:Utterance {text: $text})", {"text": utterance})
            tx.run("MATCH (f:Flow {flow_id: $flow_id}), (u:Utterance {text: $text}) MERGE (f)-[:EXEMPLIFIES]->(u)", {"flow_id": record.flow_id, "text": utterance})

    @staticmethod
    def _upsert_task_action(tx: Any, flow_id: str, task: str, action: dict[str, Any], relationship: str) -> None:
        tx.run(
            "MERGE (a:Action {action: $action}) "
            "SET a.type = $type, a.operation = $operation, a.resource = $resource, "
            "a.label = $label, a.triggers = $triggers, a.description = $description",
            action,
        )
        tx.run(
            f"MATCH (t:UserTask {{task: $task}}), (a:Action {{action: $action}}) MERGE (t)-[:{relationship}]->(a)",
            {"task": task, "action": action["action"]},
        )
        tx.run("MATCH (f:Flow {flow_id: $flow_id}), (a:Action {action: $action}) MERGE (f)-[:USES_ACTION]->(a)", {"flow_id": flow_id, "action": action["action"]})

    @staticmethod
    def _upsert_task_user_action(tx: Any, flow_id: str, task: str, action: dict[str, Any]) -> None:
        tx.run(
            "MERGE (ua:UserAction {action_id: $action_id}) "
            "SET ua.type = $type, ua.implementation_type = $implementation_type, ua.tool_id = $tool_id, "
            "ua.tool_ids = $tool_ids, ua.label = $label, ua.lifecycle_state = $lifecycle_state, "
            "ua.triggers = $triggers, ua.description = $description",
            {
                "action_id": action.get("action_id") or action.get("action"),
                "type": action.get("type"),
                "implementation_type": action.get("implementation_type"),
                "lifecycle_state": action.get("lifecycle_state") or "not_started",
                "tool_id": action.get("tool_id"),
                "tool_ids": action.get("tool_ids") or ([action.get("tool_id")] if action.get("tool_id") else []),
                "label": action.get("label"),
                "triggers": action.get("triggers"),
                "description": action.get("description"),
            },
        )
        tx.run(
            "MATCH (t:UserTask {task: $task}), (ua:UserAction {action_id: $action_id}) "
            "MERGE (t)-[:USES_USER_ACTION]->(ua)",
            {"task": task, "action_id": action.get("action_id") or action.get("action")},
        )
        tx.run(
            "MATCH (f:Flow {flow_id: $flow_id}), (ua:UserAction {action_id: $action_id}) "
            "MERGE (f)-[:USES_USER_ACTION]->(ua)",
            {"flow_id": flow_id, "action_id": action.get("action_id") or action.get("action")},
        )

    @staticmethod
    def _upsert_task_tool(tx: Any, flow_id: str, task: str, tool: dict[str, Any]) -> None:
        tx.run(
            "MERGE (tool:Tool {tool_id: $tool_id}) "
            "SET tool.tool_type = $tool_type, tool.operation = $operation, tool.resource = $resource, "
            "tool.label = $label, tool.description = $description, tool.frontend_event = $frontend_event, "
            "tool.backend_protocol = $backend_protocol, tool.endpoint = $endpoint, "
            "tool.llm_operation = $llm_operation, tool.llm_model = $llm_model, "
            "tool.llm_provider = $llm_provider, tool.requires_approval = $requires_approval",
            {
                **{
                    "label": None,
                    "description": None,
                    "frontend_event": None,
                    "backend_protocol": None,
                    "endpoint": None,
                    "llm_operation": None,
                    "llm_model": None,
                    "llm_provider": None,
                    "requires_approval": False,
                },
                **tool,
            },
        )
        tx.run(
            "MATCH (t:UserTask {task: $task}), (tool:Tool {tool_id: $tool_id}) "
            "MERGE (t)-[:USES_TOOL]->(tool)",
            {"task": task, "tool_id": tool["tool_id"]},
        )
        tx.run(
            "MATCH (f:Flow {flow_id: $flow_id}), (tool:Tool {tool_id: $tool_id}) "
            "MERGE (f)-[:USES_TOOL]->(tool)",
            {"flow_id": flow_id, "tool_id": tool["tool_id"]},
        )

    @staticmethod
    def _upsert_asset(tx: Any, asset: EnterpriseAsset) -> None:
        labels = Neo4jKnowledgeBaseGraphAdapter._labels_for_asset(asset)
        id_key, id_value = Neo4jKnowledgeBaseGraphAdapter._identity_for_asset(asset)
        label_string = ":".join(labels)

        # Determine primary_kb from owner or payload
        primary_kb = (
            getattr(asset, "owner", None)
            or asset.payload.get("primary_kb")
            or asset.payload.get("owner")
            or asset.payload.get("knowledge_base")
            or ""
        )

        # Determine engine(s) based on asset_type and projection rules
        engines = Neo4jKnowledgeBaseGraphAdapter._engines_for_asset(asset)

        tx.run(
            f"MERGE (n:{label_string} {{{id_key}: $identity_value}}) "
            "SET n.placeholder = false, n.asset_id = $asset_id, n.asset_type = $asset_type, n.name = $name, "
            "n.version = $version, n.status = $status, n.owner = $owner, "
            "n.description = $description, n.text = $text, n.tags = $tags, "
            "n.source_refs = $source_refs, n.payload_json = $payload_json, "
            "n.structural_layer = $structural_layer, n.business_layer = $business_layer, n.subtype = $subtype, "
            "n.launcher_enabled = $launcher_enabled, n.primary_kb = $primary_kb, n.engine = $engine",
            {
                "identity_value": id_value,
                "asset_id": asset.asset_id,
                "asset_type": asset.asset_type,
                "name": asset.name,
                "version": asset.version,
                "status": asset.status,
                "owner": asset.owner,
                "description": asset.description,
                "text": asset.text,
                "tags": asset.tags,
                "source_refs": asset.source_refs,
                "payload_json": json.dumps(asset.payload, ensure_ascii=False),
                "structural_layer": (
                    getattr(asset, "structural_layer", None)
                    or asset.payload.get("structural_layer")
                    or getattr(asset, "business_layer", None)
                    or asset.payload.get("business_layer")
                ),
                "business_layer": getattr(asset, "business_layer", None) or asset.payload.get("business_layer"),
                "subtype": asset.payload.get("subtype"),
                "launcher_enabled": asset.payload.get("launcher_enabled") is True,
                "primary_kb": primary_kb,
                "engine": ",".join(sorted(engines)) if engines else "",
            },
        )

        # Create OWNED_BY relationship to KnowledgeBase node
        if primary_kb:
            tx.run(
                "MERGE (kb:KnowledgeBase {name: $kb_name}) "
                "SET kb.kind = 'knowledge_base' "
                "WITH kb "
                "MATCH (a:Asset {asset_id: $asset_id}) "
                "MERGE (a)-[:OWNED_BY]->(kb)",
                {"kb_name": primary_kb, "asset_id": asset.asset_id},
            )

        # Create STORED_IN relationships to Engine nodes
        for engine_name in engines:
            tx.run(
                "MERGE (eng:Engine {name: $engine_name}) "
                "SET eng.dimension = 'engine' "
                "WITH eng "
                "MATCH (a:Asset {asset_id: $asset_id}) "
                "MERGE (a)-[:STORED_IN]->(eng)",
                {"engine_name": engine_name, "asset_id": asset.asset_id},
            )

        structural_layer = (
            getattr(asset, "structural_layer", None)
            or asset.payload.get("structural_layer")
            or getattr(asset, "business_layer", None)
            or asset.payload.get("business_layer")
        )
        if asset.asset_type == "entity" and structural_layer:
            tx.run(
                "MERGE (layer:StructuralLayer {name: $structural_layer}) "
                "SET layer.description = $description, layer.dimension = 'structural_layer' "
                "WITH layer "
                "MATCH (entity:Asset {asset_id: $asset_id}) "
                "MERGE (layer)-[:CLASSIFIES {relation_type: 'classifies'}]->(entity)",
                {
                    "structural_layer": structural_layer,
                    "asset_id": asset.asset_id,
                    "description": Neo4jKnowledgeBaseGraphAdapter._layer_description(structural_layer),
                },
            )
        tx.run(
            "MATCH (n:Asset {asset_id: $asset_id})-[r]->() "
            "WHERE r.relation_type IS NOT NULL OR type(r) = 'RELATES_TO_ASSET' "
            "DELETE r",
            {"asset_id": asset.asset_id},
        )
        for relation in asset.relations:
            target_labels, target_id_key, target_id_value = Neo4jKnowledgeBaseGraphAdapter._target_identity(relation.target_asset_id)
            tx.run(
                f"MERGE (target:{':'.join(target_labels)} {{{target_id_key}: $target_identity_value}}) "
                "ON CREATE SET target.asset_id = $target_asset_id, target.placeholder = true "
                "ON MATCH SET target.asset_id = coalesce(target.asset_id, $target_asset_id)",
                {
                    "target_identity_value": target_id_value,
                    "target_asset_id": relation.target_asset_id,
                },
            )
            rel_type = Neo4jKnowledgeBaseGraphAdapter._relationship_type(relation.type)
            tx.run(
                f"MATCH (source:Asset {{asset_id: $source_asset_id}}), (target:Asset {{asset_id: $target_asset_id}}) "
                f"MERGE (source)-[r:{rel_type}]->(target) "
                "SET r.relation_type = $relation_type, r.metadata = $metadata "
                "MERGE (source)-[:RELATES_TO_ASSET]->(target)",
                {
                    "source_asset_id": asset.asset_id,
                    "target_asset_id": relation.target_asset_id,
                    "relation_type": relation.type,
                    "metadata": json.dumps(relation.metadata, ensure_ascii=False),
                },
            )

    @staticmethod
    def _asset_from_row(row: dict[str, Any]) -> EnterpriseAsset:
        raw_asset = row.get("asset") or {}
        payload_json = raw_asset.get("payload_json")
        payload = json.loads(payload_json) if payload_json else {}
        relations = []
        for raw_relation in row.get("relations") or []:
            metadata = raw_relation.get("metadata")
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except json.JSONDecodeError:
                    metadata = {}
            relations.append(
                {
                    "type": raw_relation.get("type") or "related_to",
                    "target_asset_id": raw_relation.get("target_asset_id"),
                    "metadata": metadata or {},
                }
            )
        return EnterpriseAsset(
            asset_id=str(raw_asset.get("asset_id") or ""),
            asset_type=str(raw_asset.get("asset_type") or "unknown"),
            name=raw_asset.get("name"),
            version=str(raw_asset.get("version") or "1.0.0"),
            status=str(raw_asset.get("status") or "approved"),
            owner=raw_asset.get("owner"),
            description=str(raw_asset.get("description") or ""),
            text=str(raw_asset.get("text") or ""),
            tags=[str(value) for value in raw_asset.get("tags") or []],
            source_refs=[str(value) for value in raw_asset.get("source_refs") or []],
            relations=relations,
            payload=payload,
            structural_layer=raw_asset.get("structural_layer") or payload.get("structural_layer") or raw_asset.get("business_layer") or payload.get("business_layer"),
            business_layer=raw_asset.get("business_layer") or payload.get("business_layer"),
        )

    @staticmethod
    def _labels_for_asset(asset: EnterpriseAsset) -> list[str]:
        specific = {
            "flow": "FlowAsset",
            "user_task": "UserTaskAsset",
            "tool": "ToolAsset",
            "entity": "Entity",
            "concept": "Entity",
            "semantic_space": "SemanticSpace",
            "business_rule": "BusinessRule",
            "ruleset": "BusinessRule",
            "plan": "Plan",
            "process": "ProcessAsset",
            "qa": "QA",
            "causality": "Causality",
            "document": "DocumentAsset",
            "configuration": "ConfigurationAsset",
            "domain": "DomainAsset",
            "module": "ModuleAsset",
            "form": "FormAsset",
            "form_version": "FormVersionAsset",
        }.get(asset.asset_type, "AssetNode")
        return ["Asset", specific]

    @staticmethod
    def _identity_for_asset(asset: EnterpriseAsset) -> tuple[str, str]:
        return "asset_id", asset.asset_id

    @staticmethod
    def _target_identity(target_asset_id: str) -> tuple[list[str], str, str]:
        asset_type = target_asset_id.split(".", 1)[0]
        labels = ["Asset", {
            "flow": "FlowAsset",
            "user_task": "UserTaskAsset",
            "tool": "ToolAsset",
            "entity": "Entity",
            "concept": "Entity",
            "semantic_space": "SemanticSpace",
            "business_rule": "BusinessRule",
            "ruleset": "BusinessRule",
            "plan": "Plan",
            "process": "ProcessAsset",
            "qa": "QA",
            "causality": "Causality",
            "document": "DocumentAsset",
            "configuration": "ConfigurationAsset",
            "domain": "DomainAsset",
            "module": "ModuleAsset",
            "form": "FormAsset",
            "form_version": "FormVersionAsset",
        }.get(asset_type, "AssetNode")]
        return labels, "asset_id", target_asset_id

    @staticmethod
    def _aliases_for_asset(asset: EnterpriseAsset) -> list[str]:
        payload = asset.payload if isinstance(asset.payload, dict) else {}
        raw_aliases = payload.get("aliases") or payload.get("concept_aliases") or []
        if isinstance(raw_aliases, dict):
            values: list[str] = []
            for aliases in raw_aliases.values():
                if isinstance(aliases, list):
                    values.extend(alias for alias in aliases if isinstance(alias, str) and alias.strip())
            raw_aliases = values
        aliases = []
        seen: set[str] = set()
        for alias in raw_aliases:
            if not isinstance(alias, str):
                continue
            text = " ".join(alias.strip().split())
            if not text:
                continue
            normalized = text.casefold()
            if normalized in {"true", "false", "none", "null", "yes", "no", "n/a"}:
                continue
            if not any(char.isalpha() for char in text):
                continue
            if normalized in seen:
                continue
            seen.add(normalized)
            aliases.append(text)
        return aliases

    @staticmethod
    def _engines_for_asset(asset: EnterpriseAsset) -> list[str]:
        """Determine which storage engines an asset is projected to."""
        asset_type = asset.asset_type
        # Engine mapping based on asset type and projection rules
        engine_map = {
            "flow": ["neo4j", "catalog"],
            "process": ["neo4j", "catalog"],
            "user_task": ["neo4j", "qdrant", "catalog"],
            "tool": ["neo4j", "qdrant", "catalog"],
            "entity": ["neo4j", "qdrant", "catalog"],
            "concept": ["neo4j", "catalog"],
            "semantic_space": ["catalog"],
            "business_rule": ["neo4j", "qdrant", "sqlite", "catalog"],
            "ruleset": ["neo4j", "qdrant", "sqlite", "catalog"],
            "plan": ["neo4j", "catalog"],
            "qa": ["qdrant", "catalog"],
            "causality": ["neo4j", "qdrant", "sqlite", "catalog"],
            "document": ["qdrant", "sqlite", "catalog"],
            "configuration": ["catalog"],
            "domain": ["catalog"],
            "module": ["catalog"],
            "asset_set": ["catalog"],
        }
        return engine_map.get(asset_type, ["catalog"])

    @staticmethod
    def _layer_description(layer_name: str) -> str:
        """Return description for a structural layer."""
        descriptions = {
            "party": "Personas o entidades externas/internas que participan",
            "organization": "Divisiones, direcciones, departamentos y estructura",
            "capability": "Funciones o centros de competencia",
            "portfolio": "Conjuntos estructurados de productos/servicios",
            "offering": "Producto o servicio individual comercializable",
            "program": "Iniciativas, campañas o planes coordinados",
            "channel": "Medios y plataformas por donde interactúa",
            "transaction": "Movimientos operativos o financieros",
            "agreement": "Contratos, políticas y consentimientos",
            "event": "Hitos, SLA y cambios de estado",
            "metric": "Indicadores y KPIs",
            "workforce": "Personas/puestos concretos dentro de la empresa",
            "workforce_role": "Roles o perfiles reutilizables",
            "business_resource": "Recursos del negocio: plataformas, sistemas, documentos",
        }
        return descriptions.get(layer_name, "")

    @staticmethod
    def _should_project_asset(asset: EnterpriseAsset) -> bool:
        # asset_set is not projected to graph (catalog/relational only)
        if asset.asset_type == "asset_set":
            return False
        if asset.asset_type == "causality":
            relation_types = {relation.type for relation in asset.relations}
            return "has_cause" in relation_types or "has_effect" in relation_types
        if asset.asset_type == "entity":
            name = (asset.name or "").casefold()
            if not name:
                return False
            if len(name.split()) > 4:
                return False
            noisy_verbs = {
                "solicita",
                "impacta",
                "registra",
                "contiene",
                "exige",
                "aporta",
                "incluye",
                "actualiza",
                "recibe",
                "valida",
                "soporta",
                "respalda",
            }
            if any(token in name.split() for token in noisy_verbs):
                return False
        return True

    @staticmethod
    def _relationship_type(value: str) -> str:
        text = re.sub(r"[^A-Za-z0-9]+", "_", value.strip()).upper()
        return text or "RELATES_TO_ASSET"

    def _query_graph_context(self, tokens: list[str]) -> list[dict[str, Any]]:
        if not tokens:
            return self._query_all_graph_context()
        with self.driver.session() as session:
            return [
                dict(record)
                for record in session.run(
                    self.FILTERED_GRAPH_CONTEXT_QUERY,
                    {"tokens": tokens, "limit": self.limit},
                )
            ]

    def _query_all_graph_context(self) -> list[dict[str, Any]]:
        with self.driver.session() as session:
            return [dict(record) for record in session.run(self.GRAPH_CONTEXT_QUERY)]

    def _query_summary(
        self,
        query: str,
        row_count: int,
        tokens: list[str],
        search_mode: str,
    ) -> dict[str, Any]:
        compact_query = " ".join(query.split())
        return {
            "query": compact_query,
            "rows_returned": row_count,
            "limit": self.limit,
            "tokens": tokens,
            "search_mode": search_mode,
        }

    def _rows_preview(self, rows: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
        preview = []
        for row in rows[:limit]:
            preview.append(
                {
                    "flow_id": row.get("flow_id"),
                    "intent": row.get("intent"),
                    "business_event": row.get("business_event"),
                    "utterances": (row.get("utterances") or [])[:5],
                    "concepts": (row.get("concepts") or [])[:8],
                    "concept_aliases": (row.get("concept_aliases") or [])[:8],
                    "user_tasks": (row.get("user_tasks") or [])[:8],
                    "tools": (row.get("tools") or [])[:8],
                    "matched_tokens": row.get("matched_tokens") or [],
                    "match_score": row.get("match_score"),
                }
            )
        return preview

    def _record_from_row(self, row: dict[str, Any]) -> KnowledgeRecord:
        raw_tasks = [
            item for item in row.get("user_tasks", [])
            if isinstance(item, dict) and item.get("task")
        ]
        user_tasks = [
            UserTask(
                user_task_id=str(item["task"]),
                task=str(item["task"]),
                type=str(item.get("type") or "user_task"),
                tools=[
                    ToolDefinition(
                        tool_id=str(tool_id),
                        tool_type="backend_tool",
                        operation=str(tool_id).split(".")[-1] if "." in str(tool_id) else None,
                        resource=str(tool_id).rsplit(".", 1)[0] if "." in str(tool_id) else None,
                    )
                    for tool_id in row.get("tools", [])
                    if tool_id
                ],
            )
            for item in sorted(raw_tasks, key=lambda value: value.get("order_index") or 0)
        ]
        concepts = [str(value) for value in row.get("concepts", []) if value]
        aliases = [str(value) for value in row.get("concept_aliases", []) if value]
        concept_aliases = {concept: aliases for concept in concepts}
        capabilities = [str(value) for value in (row.get("capabilities") or row.get("tools") or []) if value]
        plan = [str(value) for value in (row.get("plan") or [task.task for task in user_tasks]) if value]
        return KnowledgeRecord(
            flow_id=str(row["flow_id"]),
            flow_name=str(row.get("flow_name") or row["flow_id"]),
            intent=str(row.get("intent") or row["flow_id"]),
            confidence=float(row.get("confidence") or 0.75),
            business_event=str(row.get("business_event") or ""),
            utterances=[str(value) for value in row.get("utterances", []) if value],
            plan=plan,
            tasks=[Task(task=task.task, type=task.type) for task in user_tasks],
            user_tasks=user_tasks,
            capabilities=capabilities,
            concepts=concepts,
            concept_aliases=concept_aliases,
            explanation=str(row.get("explanation") or "Matched from graph knowledge base."),
            source=str(row.get("source") or self.neo4j_uri),
            metadata={"knowledge_provider": "neo4j"},
        )

    @classmethod
    def _context_text(cls, row: dict[str, Any]) -> str:
        return "\n".join(
            [
                f"flow_id: {row.get('flow_id')}",
                f"flow_name: {row.get('flow_name')}",
                f"intent: {row.get('intent')}",
                f"business_event: {row.get('business_event')}",
                f"utterances: {cls._context_list(row.get('utterances'))}",
                f"concepts: {cls._context_list(row.get('concepts'))}",
                f"concept_aliases: {cls._context_list(row.get('concept_aliases'))}",
                f"user_tasks: {cls._context_list(row.get('user_tasks'))}",
                f"tools: {cls._context_list(row.get('tools'))}",
                f"explanation: {row.get('explanation') or ''}",
            ]
        )

    @classmethod
    def _context_list(cls, values: Any) -> str:
        if values is None:
            return ""
        if not isinstance(values, list):
            values = [values]
        formatted = [cls._context_value(value) for value in values]
        return ", ".join(value for value in formatted if value)

    @staticmethod
    def _context_value(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, dict):
            if value.get("task"):
                parts = [str(value["task"])]
                if value.get("type"):
                    parts.append(f"type={value['type']}")
                return " ".join(parts)
            return json.dumps(value, ensure_ascii=False, sort_keys=True)
        return str(value)
