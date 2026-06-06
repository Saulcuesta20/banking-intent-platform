from __future__ import annotations

from typing import Any, NotRequired, TypedDict


class IngestionAgentState(TypedDict, total=False):
    run_id: str
    raw_path: str
    source_files: list[str]
    semantic_analysis: dict[str, Any]
    candidate_assets: dict[str, list[dict[str, Any]]]
    validation_errors: list[str]
    review_required: bool
    written_paths: list[str]
    trace_events: list[dict[str, Any]]


class AskAgentState(TypedDict, total=False):
    question: str
    understanding: dict[str, Any]
    search_terms: list[str]
    source_routes: list[dict[str, Any]]
    evidence_bundle: dict[str, Any]
    known_targets: dict[str, list[dict[str, Any]]]
    planning_trace: dict[str, Any]
    selected_route: dict[str, Any]
    answer: dict[str, Any]
    execution_options: list[dict[str, Any]]
    approval: dict[str, Any]
    trace_events: NotRequired[list[dict[str, Any]]]

