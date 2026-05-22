#!/usr/bin/env python3
"""Query Neo4j and print Flow nodes and their neighbors as a tree.

Usage:
  ./.venv/bin/python tools/neo4j_tree.py            # print all flows
  ./.venv/bin/python tools/neo4j_tree.py --source data/flows/loan.flow.json

Set env: NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD if different from defaults.
"""
from __future__ import annotations

import os
import argparse
import json
from neo4j import GraphDatabase
from typing import Dict, List, Any


def get_driver():
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "banking-intent-dev")
    return GraphDatabase.driver(uri, auth=(user, password))


def fetch_records(driver, source: str | None = None) -> List[Dict[str, Any]]:
    query = (
        "MATCH (f:Flow)"
        " OPTIONAL MATCH (f)-[rel]->(n)"
        " WHERE $source IS NULL OR f.source = $source OR f.flow_id = $source"
        " RETURN f.source AS source, f.flow_id AS flow_id, f.flow_name AS flow_name, "
        "f.intent AS intent, type(rel) AS reltype, labels(n) AS labels, n AS node"
    )
    results = []
    with driver.session() as session:
        for rec in session.run(query, source=source):
            results.append(dict(rec))
    return results


def fetch_paths(driver, source: str | None = None, depth: int = 2) -> List[Dict[str, Any]]:
    """Return paths starting from Flow up to length `depth`.

    Each row contains: source, nodes (list), rels (list)
    """
    if depth < 1:
        raise ValueError("--depth must be 1 or greater")
    query = (
        f"MATCH p=(f:Flow)-[*1..{depth}]->(n)"
        " WHERE $source IS NULL OR f.source = $source OR f.flow_id = $source"
        " RETURN f.source AS source, f.flow_id AS flow_id, f.flow_name AS flow_name, "
        "nodes(p) AS nodes, relationships(p) AS rels, f.intent AS intent"
    )
    rows = []
    with driver.session() as session:
        for rec in session.run(query, source=source):
            rows.append(dict(rec))
    return rows


def build_tree(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
    # Legacy build (single-hop rows) is preserved but we also build nested trees from paths
    tree: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        # If row contains 'nodes' it's from paths query
        if "nodes" in row and row.get("nodes"):
            src = row.get("source") or "unknown"
            intent = row.get("intent")
            flow_id = row.get("flow_id")
            flow_name = row.get("flow_name")
            if src not in tree:
                tree[src] = {"_intent": intent, "_flow_id": flow_id, "_flow_name": flow_name, "children": []}
            # we will insert the path into the nested children
            nodes = row.get("nodes") or []
            rels = row.get("rels") or []
            # start at root children list
            current_children = tree[src]["children"]

            for i, rel in enumerate(rels):
                rel_type = rel.type if hasattr(rel, "type") else str(rel)
                try:
                    rel_props = dict(rel)
                except Exception:
                    rel_props = {}
                target_node = nodes[i + 1]
                # extract minimal props
                try:
                    props = {k: v for k, v in dict(target_node).items() if k != "__id__"}
                except Exception:
                    props = dict(target_node)

                label_list = list(target_node.labels) if hasattr(target_node, "labels") else (row.get("labels") or [])
                label_str = "|".join(label_list) if label_list else "Node"

                # find existing child with same rel and identity
                found = None
                for child in current_children:
                    if child.get("rel") == rel_type and child.get("label") == label_str and child.get("props") == props:
                        found = child
                        break

                if not found:
                    new_child = {"rel": rel_type, "rel_props": rel_props, "label": label_str, "props": props, "children": []}
                    current_children.append(new_child)
                    found = new_child

                # descend
                current_children = found["children"]

        else:
            # fallback single-row structure
            src = row.get("source") or "unknown"
            intent = row.get("intent")
            flow_id = row.get("flow_id")
            flow_name = row.get("flow_name")
            rel = row.get("reltype") or "ROOT"
            labels = row.get("labels") or []
            node = row.get("node")
            if src not in tree:
                tree[src] = {"_intent": intent, "_flow_id": flow_id, "_flow_name": flow_name, "children": []}
            label_str = "|".join(labels) if labels else "Node"
            node_props = {k: v for k, v in dict(node).items() if k != "__id__"}
            tree[src]["children"].append({"rel": rel, "rel_props": {}, "label": label_str, "props": node_props, "children": []})

    return tree


def print_tree(tree: Dict[str, Dict[str, Any]]):
    def node_display(node: Dict[str, Any]) -> str:
        props = node.get("props", {})
        if "task" in props:
            display = props.get("task")
        elif "action" in props:
            display = props.get("action")
        elif "name" in props:
            display = props.get("name")
        elif "text" in props:
            display = (props.get("text") or "").strip()[:80]
        else:
            display = json.dumps(props, ensure_ascii=False)
        rel_props = node.get("rel_props", {})
        sequence = rel_props.get("sequence")
        prefix = f"{node.get('rel')}[{sequence}]" if sequence is not None else node.get("rel")
        return f"{prefix} -> {node.get('label')}: {display}"

    def print_children(children: List[Dict[str, Any]], indent: str = "  "):
        ordered = sorted(
            children,
            key=lambda node: (
                node.get("rel") != "HAS_USER_TASK",
                node.get("rel_props", {}).get("sequence", 9999),
                node.get("rel", ""),
                str(node.get("props", {})),
            ),
        )
        for node in ordered:
            print(f"{indent}- {node_display(node)}")
            print_children(node.get("children", []), indent + "  ")

    for source, data in tree.items():
        print(f"Flow: {data.get('_flow_id')}  ({data.get('_flow_name')})")
        print(f"  source={source} intent={data.get('_intent')}")
        print_children(data.get("children", []))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", help="Filter by flow source path or flow_id", default=None)
    parser.add_argument("--json", help="Output JSON instead of pretty text", action="store_true")
    parser.add_argument("--depth", help="Recursion depth for nested tree (default 2)", type=int, default=2)
    args = parser.parse_args()

    driver = get_driver()
    try:
        rows = fetch_paths(driver, source=args.source, depth=args.depth)
    except Exception as exc:
        print("Failed to query Neo4j:", exc)
        return
    if not rows:
        print("No flow paths found in Neo4j (check connection and imported flows).")
        return
    tree = build_tree(rows)
    if args.json:
        print(json.dumps(tree, ensure_ascii=False, indent=2))
    else:
        print_tree(tree)


if __name__ == "__main__":
    main()
