#!/usr/bin/env python3
"""Push flow JSON records into Neo4j as nodes and relationships.

Usage:
  NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD can be set as env vars.
  ./.venv/bin/python tools/push_flows_to_neo4j.py --clear
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from neo4j import GraphDatabase

from app.ontology.service import OntologyTermNormalizer


def get_driver():
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "banking-intent-dev")
    return GraphDatabase.driver(uri, auth=(user, password))


def create_constraints(tx):
    tx.run("CREATE CONSTRAINT IF NOT EXISTS FOR (f:Flow) REQUIRE f.flow_id IS UNIQUE")
    tx.run("CREATE CONSTRAINT IF NOT EXISTS FOR (a:Action) REQUIRE a.action IS UNIQUE")
    tx.run("CREATE CONSTRAINT IF NOT EXISTS FOR (o:Ontology) REQUIRE o.name IS UNIQUE")
    tx.run("CREATE CONSTRAINT IF NOT EXISTS FOR (s:Synonym) REQUIRE s.term IS UNIQUE")
    tx.run("CREATE CONSTRAINT IF NOT EXISTS FOR (t:UserTask) REQUIRE t.task IS UNIQUE")
    tx.run("CREATE CONSTRAINT IF NOT EXISTS FOR (u:Utterance) REQUIRE u.text IS UNIQUE")


def upsert_record(tx, record: dict[str, Any]) -> None:
    flow_id = record.get("flow_id", record.get("intent"))
    source = record.get("source", "unknown")
    tx.run(
        "MERGE (f:Flow {flow_id: $flow_id}) "
        "SET f.flow_name = $flow_name, f.source = $source, f.intent = $intent, "
        "f.business_event = $business_event, f.explanation = $explanation, f.confidence = $confidence",
        {
            "flow_id": flow_id,
            "flow_name": record.get("flow_name", record.get("intent")),
            "source": source,
            "intent": record.get("intent"),
            "business_event": record.get("business_event"),
            "explanation": record.get("explanation"),
            "confidence": float(record.get("confidence", 0.0)),
        },
    )

    for cap in record.get("capabilities", []):
        tx.run(
            "MERGE (a:Action {action: $action}) "
            "SET a.type = coalesce(a.type, 'declared_action'), a.source = coalesce(a.source, 'flow')",
            {"action": cap},
        )
        tx.run(
            "MATCH (f:Flow {flow_id: $flow_id}), (a:Action {action: $action}) "
            "MERGE (f)-[:DECLARES_ACTION]->(a)",
            {"flow_id": flow_id, "action": cap},
        )

    ontology_nodes = record.get("ontology_nodes", [])
    ontology_aliases = record.get("ontology_aliases") or OntologyTermNormalizer().build_aliases_for_ontology_nodes(
        [str(node) for node in ontology_nodes]
    )
    for node in ontology_nodes:
        tx.run("MERGE (o:Ontology {name: $node})", {"node": node})
        tx.run(
            "MATCH (f:Flow {flow_id: $flow_id}), (o:Ontology {name: $node}) "
            "MERGE (f)-[:HAS_ONTOLOGY]->(o)",
            {"flow_id": flow_id, "node": node},
        )
        for alias in ontology_aliases.get(node, []):
            tx.run(
                "MERGE (s:Synonym {term: $alias}) "
                "SET s.normalized = true",
                {"alias": alias},
            )
            tx.run(
                "MATCH (o:Ontology {name: $node}), (s:Synonym {term: $alias}) "
                "MERGE (o)-[:HAS_SYNONYM]->(s) "
                "MERGE (s)-[:NORMALIZES_TO]->(o)",
                {"node": node, "alias": alias},
            )

    user_tasks = record.get("user_tasks") or record.get("tasks", [])
    for index, task in enumerate(user_tasks, start=1):
        if not isinstance(task, dict):
            continue
        task_name = task.get("task")
        if not task_name:
            continue
        sequence = int(task.get("sequence", index))
        tx.run(
            "MERGE (t:UserTask {task: $task}) "
            "SET t.type = $type",
            {"task": task_name, "type": task.get("type")},
        )
        tx.run(
            "MATCH (f:Flow {flow_id: $flow_id}), (t:UserTask {task: $task}) "
            "MERGE (f)-[rel:HAS_USER_TASK]->(t) "
            "SET rel.sequence = $sequence",
            {"flow_id": flow_id, "task": task_name, "sequence": sequence},
        )

        for action in task.get("front_actions", []):
            action_payload = {
                "action": action["action"],
                "type": "front_action",
                "operation": action.get("operation"),
                "resource": action.get("resource"),
                "label": action.get("label"),
                "triggers": action.get("triggers"),
                "description": action.get("description"),
            }
            tx.run(
                "MERGE (a:Action {action: $action}) "
                "SET a.type = $type, a.operation = $operation, a.resource = $resource, "
                "a.label = $label, a.triggers = $triggers, a.description = $description",
                action_payload,
            )
            tx.run(
                "MATCH (t:UserTask {task: $task}), (a:Action {action: $action}) "
                "MERGE (t)-[:HAS_FRONT_ACTION]->(a)",
                {"task": task_name, "action": action["action"]},
            )
            tx.run(
                "MATCH (f:Flow {flow_id: $flow_id}), (a:Action {action: $action}) "
                "MERGE (f)-[:USES_ACTION]->(a)",
                {"flow_id": flow_id, "action": action["action"]},
            )

        for action in task.get("back_actions", []):
            action_payload = {
                "action": action["action"],
                "type": "back_action",
                "operation": action.get("operation"),
                "resource": action.get("resource"),
                "label": action.get("label"),
                "triggers": action.get("triggers"),
                "description": action.get("description"),
            }
            tx.run(
                "MERGE (a:Action {action: $action}) "
                "SET a.type = $type, a.operation = $operation, a.resource = $resource, "
                "a.label = $label, a.triggers = $triggers, a.description = $description",
                action_payload,
            )
            tx.run(
                "MATCH (t:UserTask {task: $task}), (a:Action {action: $action}) "
                "MERGE (t)-[:HAS_BACK_ACTION]->(a)",
                {"task": task_name, "action": action["action"]},
            )
            tx.run(
                "MATCH (f:Flow {flow_id: $flow_id}), (a:Action {action: $action}) "
                "MERGE (f)-[:USES_ACTION]->(a)",
                {"flow_id": flow_id, "action": action["action"]},
            )

    for utterance in record.get("utterances", [])[:20]:
        tx.run("MERGE (u:Utterance {text: $text})", {"text": utterance})
        tx.run(
            "MATCH (f:Flow {flow_id: $flow_id}), (u:Utterance {text: $text}) "
            "MERGE (f)-[:EXEMPLIFIES]->(u)",
            {"flow_id": flow_id, "text": utterance},
        )


def clear_imported_graph(tx):
    tx.run(
        "MATCH (n) "
        "WHERE n:Flow OR n:KnowledgeRecord OR n:Action OR n:Capability OR n:Ontology OR n:Task "
        "OR n:UserTask OR n:FrontAction OR n:BackAction OR n:Utterance OR n:Synonym "
        "DETACH DELETE n"
    )


def load_user_tasks(flow_dir: Path) -> dict[str, dict[str, Any]]:
    catalog: dict[str, dict[str, Any]] = {}
    roots = [flow_dir.parent / "user_tasks", flow_dir]
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.user_task.json")):
            record = json.loads(path.read_text(encoding="utf-8"))
            catalog[record["user_task_id"]] = record
            catalog[record["task"]] = record
    return catalog


def resolve_user_task_refs(record: dict[str, Any], catalog: dict[str, dict[str, Any]]) -> dict[str, Any]:
    refs = record.get("user_task_refs")
    if not isinstance(refs, list):
        return record

    user_tasks = []
    for index, ref in enumerate(refs, start=1):
        if isinstance(ref, str):
            ref_id = ref
            sequence = index
        elif isinstance(ref, dict):
            ref_id = str(ref.get("user_task_id") or ref.get("task"))
            sequence = int(ref.get("sequence", index))
        else:
            continue
        task = catalog.get(ref_id)
        if task is None:
            continue
        user_tasks.append({**task, "sequence": sequence})
    return {**record, "user_tasks": user_tasks}


def load_flows(flow_dir: Path) -> list[dict[str, Any]]:
    records = []
    seen_flow_ids = set()
    user_task_catalog = load_user_tasks(flow_dir)
    for path in sorted(flow_dir.glob("*.json")):
        if ".user_task" in path.name:
            continue
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            flow_id = record.get("flow_id") or record.get("intent")
            if not flow_id or flow_id in seen_flow_ids:
                flow_id = path.stem
                record["flow_id"] = flow_id
            record["source"] = str(path)
            record = resolve_user_task_refs(record, user_task_catalog)
            seen_flow_ids.add(flow_id)
            records.append(record)
        except Exception as exc:
            print("Failed to load", path, exc)
    return records


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clear", action="store_true", help="Delete imported flow graph nodes before loading.")
    parser.add_argument("--flow-dir", default="data/flows", help="Directory containing .flow.json files.")
    args = parser.parse_args()

    flow_dir = Path(args.flow_dir)
    if not flow_dir.exists():
        print(f"No flow directory found at {flow_dir}")
        sys.exit(2)

    records = load_flows(flow_dir)
    if not records:
        print(f"No flow JSON files found in {flow_dir}")
        sys.exit(0)

    driver = get_driver()
    with driver.session() as session:
        if args.clear:
            session.execute_write(clear_imported_graph)
        session.execute_write(create_constraints)
        for rec in records:
            session.execute_write(upsert_record, rec)

    print(f"Imported {len(records)} flow records into Neo4j")


if __name__ == "__main__":
    main()
