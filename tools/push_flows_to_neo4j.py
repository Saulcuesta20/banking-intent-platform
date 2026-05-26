#!/usr/bin/env python3
"""Load approved flow artifacts into the Neo4j knowledge graph."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from app.ingestion.flow_loader import FlowKnowledgeLoader
from app.knowledge_graph.neo4j import Neo4jKnowledgeGraphRepository
from app.knowledge_graph.service import KnowledgeGraphService


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clear", action="store_true", help="Delete knowledge graph nodes before loading.")
    parser.add_argument("--flow-dir", default="data/flows", help="Directory containing flow JSON files.")
    args = parser.parse_args()

    flow_dir = Path(args.flow_dir)
    if not flow_dir.exists():
        print(f"No flow directory found at {flow_dir}")
        sys.exit(2)

    records = FlowKnowledgeLoader().load_directory(flow_dir)
    if not records:
        print(f"No flow JSON files found in {flow_dir}")
        return

    repository = Neo4jKnowledgeGraphRepository(
        flow_directory=flow_dir,
        neo4j_uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        neo4j_user=os.getenv("NEO4J_USER", "neo4j"),
        neo4j_password=os.getenv("NEO4J_PASSWORD", "banking-intent-dev"),
    )
    if args.clear:
        repository.clear()
    KnowledgeGraphService(repository).ingest(records)

    print(f"Imported {len(records)} flow records into the Neo4j knowledge graph")


if __name__ == "__main__":
    main()
