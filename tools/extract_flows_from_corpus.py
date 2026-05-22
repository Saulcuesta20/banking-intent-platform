#!/usr/bin/env python3
"""Extract flow and user task JSON files from raw corpus using an LLM.

Default behavior writes to data/generated so results can be reviewed.
Use --apply to replace data/flows and data/user_tasks.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ingestion.llm_flow_loader import (
    CorpusFlowLoader,
    FlowExtractionError,
    OpenAICompatibleLLMClient,
)
from app.ingestion.pipeline import (
    IngestionPipelineConfig,
    IngestionPipelineService,
    LangGraphIngestionPipelineService,
)
from app.ingestion.reasoning import (
    AutoGenIngestionReasoningProvider,
    IngestionReasoningService,
    RoleBasedIngestionReasoningProvider,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", default="data/raw", help="Directory containing corpus files.")
    parser.add_argument("--out-dir", default="data/generated", help="Preview output directory.")
    parser.add_argument("--flow-dir", default="data/flows", help="Target flow directory when --apply is used.")
    parser.add_argument("--user-task-dir", default="data/user_tasks", help="Target user task directory when --apply is used.")
    parser.add_argument("--action-registry-dir", default="data/action_registry", help="Target action registry directory when --apply is used.")
    parser.add_argument("--audit-dir", default="data/processed/ingestion_audit", help="Directory for deterministic ingestion audit records.")
    parser.add_argument("--model", default=None, help="LLM model. Defaults to FLOW_EXTRACTOR_MODEL or gpt-4o-mini.")
    parser.add_argument("--reasoning-model", default=None, help="AutoGen reasoning model. Defaults to INGESTION_REASONING_MODEL, FLOW_EXTRACTOR_MODEL, or gpt-4o-mini.")
    parser.add_argument("--max-pdf-image-pages", type=int, default=3, help="Max PDF pages to render as images when PDF text is unavailable.")
    parser.add_argument("--ingestion-reasoning", action="store_true", help="Add role-based ingestion reasoning guidance before LLM extraction.")
    parser.add_argument("--autogen-ingestion-reasoning", action="store_true", help="Run AutoGen ingestion agents before LLM extraction.")
    parser.add_argument("--langgraph", action="store_true", help="Use LangGraph to orchestrate ingestion branches and retries.")
    parser.add_argument("--max-validation-retries", type=int, default=0, help="Retries for LangGraph validation/extraction failures.")
    parser.add_argument("--require-human-review", action="store_true", help="Mark the run as requiring human review in audit metadata.")
    parser.add_argument("--apply", action="store_true", help="Write directly to data/flows and data/user_tasks.")
    parser.add_argument("--clean", action="store_true", help="Delete existing generated files in the target directories first.")
    parser.add_argument("--print-json", action="store_true", help="Print normalized extraction JSON to stdout.")
    args = parser.parse_args()

    reasoning_mode = "none"
    reasoning_service = None
    if args.autogen_ingestion_reasoning:
        reasoning_mode = "autogen"
        reasoning_service = IngestionReasoningService(
            AutoGenIngestionReasoningProvider(model=args.reasoning_model)
        )
    elif args.ingestion_reasoning:
        reasoning_mode = "role_based"
        reasoning_service = IngestionReasoningService(RoleBasedIngestionReasoningProvider())

    loader = CorpusFlowLoader(
        OpenAICompatibleLLMClient(model=args.model),
        max_pdf_image_pages=args.max_pdf_image_pages,
        reasoning_service=reasoning_service,
    )

    if args.apply:
        flow_dir = Path(args.flow_dir)
        user_task_dir = Path(args.user_task_dir)
        action_registry_dir = Path(args.action_registry_dir)
    else:
        preview_dir = Path(args.out_dir)
        flow_dir = preview_dir / "flows"
        user_task_dir = preview_dir / "user_tasks"
        action_registry_dir = preview_dir / "action_registry"

    pipeline = LangGraphIngestionPipelineService(loader) if args.langgraph else IngestionPipelineService(loader)
    try:
        result = pipeline.run(
            IngestionPipelineConfig(
                raw_path=Path(args.raw_dir),
                flow_directory=flow_dir,
                user_task_directory=user_task_dir,
                action_registry_directory=action_registry_dir,
                audit_directory=Path(args.audit_dir),
                clean=args.clean,
                apply=args.apply,
                reasoning_mode=reasoning_mode,
                max_validation_retries=args.max_validation_retries,
                require_human_review=args.require_human_review,
            )
        )
    except FlowExtractionError as exc:
        raise SystemExit(f"Flow extraction failed: {exc}") from exc

    if args.print_json:
        print(json.dumps(result.extraction_result, ensure_ascii=False, indent=2))

    print(
        f"Extraction {result.mode}: wrote {result.flows_written} flows to {result.flow_directory} "
        f"{result.user_tasks_written} user tasks to {result.user_task_directory}, "
        f"and {result.actions_written} actions to {result.action_registry_directory}. "
        f"Audit: {result.audit_path}"
    )


if __name__ == "__main__":
    main()
