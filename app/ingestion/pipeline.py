from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from importlib import import_module
from pathlib import Path
from typing import Any, Literal, TypedDict

from app.ingestion.llm_flow_loader import CorpusDocument, CorpusFlowLoader, FlowExtractionError
from app.ingestion.semantic_analyzer import (
    HeuristicSemanticAnalyzerProvider,
    SemanticAnalysisResult,
    SemanticAnalyzerService,
)


@dataclass(frozen=True)
class IngestionPipelineConfig:
    raw_path: Path
    flow_directory: Path
    user_task_directory: Path
    action_registry_directory: Path
    audit_directory: Path
    clean: bool = False
    apply: bool = False
    reasoning_mode: str = "none"
    max_validation_retries: int = 0
    require_human_review: bool = False
    semantic_analysis: bool = True


@dataclass(frozen=True)
class IngestionPipelineResult:
    mode: str
    flow_directory: Path
    user_task_directory: Path
    action_registry_directory: Path
    audit_path: Path
    source_files: list[str]
    flows_written: int
    user_tasks_written: int
    actions_written: int
    steps: list[dict[str, Any]] = field(default_factory=list)
    extraction_result: dict[str, Any] = field(default_factory=dict)
    semantic_analysis_result: dict[str, Any] = field(default_factory=dict)


class IngestionPipelineService:
    """Deterministic ingestion pipeline coordinator.

    Agents and LLMs may recommend or extract candidate structures, but this
    service owns the sequence, audit trail, and write boundary.
    """

    def __init__(self, loader: CorpusFlowLoader):
        self.loader = loader
        self.semantic_analyzer = SemanticAnalyzerService(HeuristicSemanticAnalyzerProvider())

    def run(self, config: IngestionPipelineConfig) -> IngestionPipelineResult:
        started_at = self._now()
        steps: list[dict[str, Any]] = []

        documents = self.loader.load_corpus(config.raw_path)
        self._record_step(
            steps,
            "scan_and_parse_corpus",
            "custom",
            "ok",
            {"documents": len(documents), "source_files": [str(doc.path) for doc in documents]},
        )

        semantic_analysis = self._analyze_semantics(config, documents, steps)
        result = self.loader.extract_documents(
            self._documents_with_semantic_context(documents, semantic_analysis)
        )
        if semantic_analysis.classifications:
            result["semantic_analysis"] = semantic_analysis.to_dict()
        self._record_step(
            steps,
            "reason_extract_validate_json",
            self._owner_for_reasoning(config.reasoning_mode),
            "ok",
            {
                "reasoning_mode": config.reasoning_mode,
                "flows": len(result["flows"]),
                "user_tasks": len(result["user_tasks"]),
                "actions": len(result["action_registry"]),
                "semantic_review_required": semantic_analysis.review_required,
            },
        )

        self.loader.write_result(
            result,
            flow_directory=config.flow_directory,
            user_task_directory=config.user_task_directory,
            action_registry_directory=config.action_registry_directory,
            clean=config.clean,
        )
        self._record_step(
            steps,
            "write_artifacts",
            "custom",
            "ok",
            {
                "mode": "apply" if config.apply else "preview",
                "flow_directory": str(config.flow_directory),
                "user_task_directory": str(config.user_task_directory),
                "action_registry_directory": str(config.action_registry_directory),
            },
        )

        audit_path = self._write_audit(
            config=config,
            documents=documents,
            result=result,
            steps=steps,
            started_at=started_at,
            semantic_analysis=semantic_analysis,
        )
        self._record_step(
            steps,
            "write_audit",
            "custom",
            "ok",
            {"audit_path": str(audit_path)},
        )
        self._rewrite_audit_with_final_steps(audit_path, steps)

        return IngestionPipelineResult(
            mode="apply" if config.apply else "preview",
            flow_directory=config.flow_directory,
            user_task_directory=config.user_task_directory,
            action_registry_directory=config.action_registry_directory,
            audit_path=audit_path,
            source_files=[str(doc.path) for doc in documents],
            flows_written=len(result["flows"]),
            user_tasks_written=len(result["user_tasks"]),
            actions_written=len(result["action_registry"]),
            steps=steps,
            extraction_result=result,
            semantic_analysis_result=semantic_analysis.to_dict(),
        )

    def _analyze_semantics(
        self,
        config: IngestionPipelineConfig,
        documents: list[CorpusDocument],
        steps: list[dict[str, Any]],
    ) -> SemanticAnalysisResult:
        if not config.semantic_analysis:
            return SemanticAnalysisResult()
        result = self.semantic_analyzer.analyze(documents)
        self._record_step(
            steps,
            "semantic_analyze_classify_corpus",
            "llm_or_heuristic_plus_human_review",
            "review_required" if result.review_required else "ok",
            {
                "classifications": len(result.classifications),
                "review_required": result.review_required,
                "summary": result.summary,
            },
        )
        return result

    def _documents_with_semantic_context(
        self,
        documents: list[CorpusDocument],
        semantic_analysis: SemanticAnalysisResult,
    ) -> list[CorpusDocument]:
        context = semantic_analysis.to_prompt_context()
        if not context:
            return documents
        return [
            *documents,
            CorpusDocument(
                path=Path("semantic_analysis_review_context.md"),
                text=context,
                kind="semantic_analysis",
            ),
        ]

    def _write_audit(
        self,
        config: IngestionPipelineConfig,
        documents: list[CorpusDocument],
        result: dict[str, Any],
        steps: list[dict[str, Any]],
        started_at: str,
        semantic_analysis: SemanticAnalysisResult,
    ) -> Path:
        config.audit_directory.mkdir(parents=True, exist_ok=True)
        audit_path = config.audit_directory / f"ingestion_run_{self._file_timestamp()}.json"
        review_required = config.require_human_review or semantic_analysis.review_required
        review_path = self._write_human_review_artifact(
            config=config,
            semantic_analysis=semantic_analysis,
            result=result,
        ) if review_required else None
        payload = {
            "started_at": started_at,
            "finished_at": self._now(),
            "mode": "apply" if config.apply else "preview",
            "reasoning_mode": config.reasoning_mode,
            "semantic_analysis": semantic_analysis.to_dict(),
            "human_review": {
                "required": review_required,
                "reason": "semantic analysis requires review" if semantic_analysis.review_required else "",
                "status": "pending" if review_required else "not_required",
                "review_path": str(review_path) if review_path else None,
            },
            "raw_path": str(config.raw_path),
            "source_files": [
                {
                    "path": str(doc.path),
                    "kind": doc.kind,
                    "sha256": self._hash_source_path(doc.path),
                }
                for doc in documents
            ],
            "outputs": {
                "flow_directory": str(config.flow_directory),
                "user_task_directory": str(config.user_task_directory),
                "action_registry_directory": str(config.action_registry_directory),
                "flows": [flow["flow_id"] for flow in result["flows"]],
                "user_tasks": [task["user_task_id"] for task in result["user_tasks"]],
                "actions": [action["action"] for action in result["action_registry"]],
            },
            "steps": steps,
        }
        audit_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return audit_path

    def _write_human_review_artifact(
        self,
        config: IngestionPipelineConfig,
        semantic_analysis: SemanticAnalysisResult,
        result: dict[str, Any],
    ) -> Path:
        review_directory = config.audit_directory.parent / "human_review"
        review_directory.mkdir(parents=True, exist_ok=True)
        review_path = review_directory / f"ingestion_review_{self._file_timestamp()}.json"
        payload = {
            "status": "pending",
            "instructions": [
                "Review semantic classifications and extracted artifacts before graph loading.",
                "Change status to approved when the artifacts can be loaded.",
                "Use reviewer_notes to document corrections, rejected flows, or missing process definitions.",
            ],
            "reviewer_notes": "",
            "semantic_analysis": semantic_analysis.to_dict(),
            "candidate_outputs": {
                "flows": [flow.get("flow_id") for flow in result.get("flows", [])],
                "user_tasks": [task.get("user_task_id") for task in result.get("user_tasks", [])],
                "actions": [action.get("action") for action in result.get("action_registry", [])],
            },
        }
        review_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return review_path

    def _rewrite_audit_with_final_steps(self, audit_path: Path, steps: list[dict[str, Any]]) -> None:
        payload = json.loads(audit_path.read_text(encoding="utf-8"))
        payload["finished_at"] = self._now()
        payload["steps"] = steps
        audit_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def _hash_source_path(self, path: Path) -> str | None:
        real_path = Path(str(path).split("#", 1)[0])
        if not real_path.exists() or not real_path.is_file():
            return None
        digest = hashlib.sha256()
        with real_path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _record_step(
        self,
        steps: list[dict[str, Any]],
        name: str,
        owner: str,
        status: str,
        metadata: dict[str, Any],
    ) -> None:
        steps.append(
            {
                "name": name,
                "owner": owner,
                "status": status,
                "timestamp": self._now(),
                "metadata": metadata,
            }
        )

    def _owner_for_reasoning(self, reasoning_mode: str) -> str:
        if reasoning_mode == "autogen":
            return "autogen_recommendation_plus_custom_validation"
        if reasoning_mode == "role_based":
            return "custom_role_guidance_plus_custom_validation"
        return "llm_extraction_plus_custom_validation"

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _file_timestamp(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


class IngestionGraphState(TypedDict, total=False):
    config: IngestionPipelineConfig
    documents: list[CorpusDocument]
    extraction_result: dict[str, Any]
    semantic_analysis_result: SemanticAnalysisResult
    steps: list[dict[str, Any]]
    started_at: str
    audit_path: Path
    attempts: int
    error: str
    final_result: IngestionPipelineResult


class LangGraphIngestionPipelineService(IngestionPipelineService):
    """LangGraph orchestration for ingestion branches and retries.

    The node bodies still call deterministic custom code. LangGraph owns graph
    routing only: retry extraction on validation failure, stop on repeated
    failure, and preserve a place for formal human-review branches.
    """

    def run(self, config: IngestionPipelineConfig) -> IngestionPipelineResult:
        graph = self._build_graph()
        final_state = graph.invoke(
            {
                "config": config,
                "steps": [],
                "attempts": 0,
                "started_at": self._now(),
            }
        )
        if final_state.get("error"):
            raise FlowExtractionError(str(final_state["error"]))
        return final_state["final_result"]

    def _build_graph(self):
        graph_module = self._optional_import("langgraph.graph", "langgraph")
        StateGraph = graph_module.StateGraph
        START = graph_module.START
        END = graph_module.END

        builder = StateGraph(IngestionGraphState)
        builder.add_node("scan_and_parse", self._scan_and_parse_node)
        builder.add_node("extract_and_validate", self._extract_and_validate_node)
        builder.add_node("write_artifacts", self._write_artifacts_node)
        builder.add_node("write_audit", self._write_audit_node)
        builder.add_node("fail", self._fail_node)

        builder.add_edge(START, "scan_and_parse")
        builder.add_edge("scan_and_parse", "extract_and_validate")
        builder.add_conditional_edges(
            "extract_and_validate",
            self._route_after_extract,
            {
                "retry": "extract_and_validate",
                "write": "write_artifacts",
                "fail": "fail",
            },
        )
        builder.add_edge("write_artifacts", "write_audit")
        builder.add_edge("write_audit", END)
        builder.add_edge("fail", END)
        return builder.compile()

    def _scan_and_parse_node(self, state: IngestionGraphState) -> dict[str, Any]:
        config = state["config"]
        steps = list(state.get("steps", []))
        documents = self.loader.load_corpus(config.raw_path)
        self._record_step(
            steps,
            "scan_and_parse_corpus",
            "custom",
            "ok",
            {"documents": len(documents), "source_files": [str(doc.path) for doc in documents]},
        )
        semantic_analysis = self._analyze_semantics(config, documents, steps)
        return {"documents": documents, "semantic_analysis_result": semantic_analysis, "steps": steps}

    def _extract_and_validate_node(self, state: IngestionGraphState) -> dict[str, Any]:
        config = state["config"]
        steps = list(state.get("steps", []))
        attempts = int(state.get("attempts", 0)) + 1
        semantic_analysis = state.get("semantic_analysis_result") or SemanticAnalysisResult()
        try:
            result = self.loader.extract_documents(
                self._documents_with_semantic_context(state.get("documents", []), semantic_analysis)
            )
        except FlowExtractionError as exc:
            self._record_step(
                steps,
                "reason_extract_validate_json",
                self._owner_for_reasoning(config.reasoning_mode),
                "retryable_error",
                {
                    "attempt": attempts,
                    "reasoning_mode": config.reasoning_mode,
                    "error": str(exc),
                },
            )
            return {
                "attempts": attempts,
                "steps": steps,
                "error": str(exc),
            }

        self._record_step(
            steps,
            "reason_extract_validate_json",
            self._owner_for_reasoning(config.reasoning_mode),
            "ok",
            {
                "attempt": attempts,
                "reasoning_mode": config.reasoning_mode,
                "flows": len(result["flows"]),
                "user_tasks": len(result["user_tasks"]),
                "actions": len(result["action_registry"]),
                "semantic_review_required": semantic_analysis.review_required,
            },
        )
        if semantic_analysis.classifications:
            result["semantic_analysis"] = semantic_analysis.to_dict()
        return {
            "attempts": attempts,
            "steps": steps,
            "error": "",
            "extraction_result": result,
        }

    def _route_after_extract(self, state: IngestionGraphState) -> Literal["retry", "write", "fail"]:
        if not state.get("error"):
            return "write"
        config = state["config"]
        if int(state.get("attempts", 0)) <= config.max_validation_retries:
            return "retry"
        return "fail"

    def _write_artifacts_node(self, state: IngestionGraphState) -> dict[str, Any]:
        config = state["config"]
        steps = list(state.get("steps", []))
        result = state["extraction_result"]
        self.loader.write_result(
            result,
            flow_directory=config.flow_directory,
            user_task_directory=config.user_task_directory,
            action_registry_directory=config.action_registry_directory,
            clean=config.clean,
        )
        self._record_step(
            steps,
            "write_artifacts",
            "custom",
            "ok",
            {
                "mode": "apply" if config.apply else "preview",
                "requires_human_review": config.require_human_review or not config.apply,
                "flow_directory": str(config.flow_directory),
                "user_task_directory": str(config.user_task_directory),
                "action_registry_directory": str(config.action_registry_directory),
            },
        )
        return {"steps": steps}

    def _write_audit_node(self, state: IngestionGraphState) -> dict[str, Any]:
        config = state["config"]
        steps = list(state.get("steps", []))
        result = state["extraction_result"]
        audit_path = self._write_audit(
            config=config,
            documents=state.get("documents", []),
            result=result,
            steps=steps,
            started_at=state["started_at"],
            semantic_analysis=state.get("semantic_analysis_result") or SemanticAnalysisResult(),
        )
        self._record_step(
            steps,
            "write_audit",
            "custom_langgraph",
            "ok",
            {"audit_path": str(audit_path)},
        )
        self._rewrite_audit_with_final_steps(audit_path, steps)
        final_result = IngestionPipelineResult(
            mode="apply" if config.apply else "preview",
            flow_directory=config.flow_directory,
            user_task_directory=config.user_task_directory,
            action_registry_directory=config.action_registry_directory,
            audit_path=audit_path,
            source_files=[str(doc.path) for doc in state.get("documents", [])],
            flows_written=len(result["flows"]),
            user_tasks_written=len(result["user_tasks"]),
            actions_written=len(result["action_registry"]),
            steps=steps,
            extraction_result=result,
            semantic_analysis_result=(state.get("semantic_analysis_result") or SemanticAnalysisResult()).to_dict(),
        )
        return {"steps": steps, "audit_path": audit_path, "final_result": final_result}

    def _fail_node(self, state: IngestionGraphState) -> dict[str, Any]:
        steps = list(state.get("steps", []))
        self._record_step(
            steps,
            "halt_ingestion",
            "langgraph",
            "failed",
            {
                "attempts": int(state.get("attempts", 0)),
                "error": state.get("error", "unknown ingestion error"),
            },
        )
        return {"steps": steps}

    def _optional_import(self, module_name: str, friendly_name: str):
        try:
            return import_module(module_name)
        except ImportError as exc:
            raise RuntimeError(
                f"Optional dependency '{friendly_name}' is required for LangGraph ingestion orchestration."
            ) from exc
