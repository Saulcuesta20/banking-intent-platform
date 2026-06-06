#!/usr/bin/env python3
"""Extract flow knowledge from raw corpus and optionally persist it to Neo4j."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ingestion.llm_flow_loader import (
    CorpusFlowLoader,
    FlowExtractionError,
    OpenAICompatibleLLMClient,
)
from app.ingestion.orchestrator import (
    IngestionOrchestratorConfig,
    IngestionOrchestratorService,
    RoleBasedExtractionInstructionBuilder,
)
from app.knowledge_base.adapters.graph.neo4j import Neo4jKnowledgeBaseGraphAdapter
from app.knowledge_base.service import KnowledgeBaseService


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", default="data/raw", help="Directory containing corpus files.")
    parser.add_argument("--audit-dir", default="data/processed/ingestion_audit", help="Directory for deterministic ingestion audit records.")
    parser.add_argument("--model", default=None, help="LLM model. Defaults to FLOW_EXTRACTOR_MODEL or gpt-4o-mini.")
    parser.add_argument("--max-pdf-image-pages", type=int, default=3, help="Max PDF pages to render as images when PDF text is unavailable.")
    parser.add_argument("--build-extraction-instructions", action="store_true", help="Build role-based extraction instructions before LLM extraction.")
    parser.add_argument("--max-validation-retries", type=int, default=0, help="Retries for LangGraph validation/extraction failures.")
    parser.add_argument("--require-human-review", action="store_true", help="Mark the run as requiring human review in audit metadata.")
    parser.add_argument("--apply", action="store_true", help="Persist extracted flows directly to the knowledge base.")
    parser.add_argument("--clean", action="store_true", help="Clear existing graph flow knowledge before applying.")
    parser.add_argument("--print-json", action="store_true", help="Print normalized extraction JSON to stdout.")
    args = parser.parse_args()

    extraction_instruction_mode = "none"
    instruction_builder = None
    if args.build_extraction_instructions:
        extraction_instruction_mode = "role_based"
        instruction_builder = RoleBasedExtractionInstructionBuilder()

    loader = CorpusFlowLoader(
        OpenAICompatibleLLMClient(model=args.model),
        max_pdf_image_pages=args.max_pdf_image_pages,
        instruction_builder=instruction_builder,
    )

    knowledge_base_service = None
    if args.apply:
        knowledge_base_service = KnowledgeBaseService(
            Neo4jKnowledgeBaseGraphAdapter(
                neo4j_uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
                neo4j_user=os.getenv("NEO4J_USER", "neo4j"),
                neo4j_password=os.getenv("NEO4J_PASSWORD", "banking-intent-dev"),
            )
        )

    orchestrator = IngestionOrchestratorService(loader)
    try:
        result = orchestrator.run(
            IngestionOrchestratorConfig(
                raw_path=Path(args.raw_dir),
                audit_directory=Path(args.audit_dir),
                knowledge_base_service=knowledge_base_service,
                clean=args.clean,
                apply=args.apply,
                extraction_instruction_mode=extraction_instruction_mode,
                max_validation_retries=args.max_validation_retries,
                require_human_review=args.require_human_review,
            )
        )
    except FlowExtractionError as exc:
        raise SystemExit(f"Flow extraction failed: {exc}") from exc

    if args.print_json:
        print(json.dumps(result.extraction_result, ensure_ascii=False, indent=2))

    print(
        f"Extraction {result.mode}: persisted {result.flows_persisted} flows, "
        f"extracted {result.user_tasks_extracted} user tasks and {result.tools_extracted} tools. "
        f"Audit: {result.audit_path}"
    )


if __name__ == "__main__":
    main()
