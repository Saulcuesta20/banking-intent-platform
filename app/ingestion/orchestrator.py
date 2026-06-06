from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from importlib import import_module
from pathlib import Path
from typing import Any, Literal, Protocol, TypedDict

from app.ingestion.llm_flow_loader import CorpusDocument, CorpusFlowLoader, FlowExtractionError
from app.ingestion.semantic_analyzer import (
    HeuristicSemanticAnalyzerProvider,
    SemanticAnalysisResult,
    SemanticAnalyzerService,
)
from app.knowledge_base.service import KnowledgeBaseService


@dataclass(frozen=True)
class ExtractionInstruction:
    agent: str
    finding: str

    def to_dict(self) -> dict[str, str]:
        return {"agent": self.agent, "finding": self.finding}


@dataclass(frozen=True)
class ExtractionInstructionSet:
    findings: list[ExtractionInstruction] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {"findings": [finding.to_dict() for finding in self.findings]}

    def to_prompt_context(self) -> str:
        if not self.findings:
            return ""
        lines = ["Role-based extraction instructions:"]
        for finding in self.findings:
            lines.append(f"- {finding.agent}: {finding.finding}")
        return "\n".join(lines)


class ExtractionInstructionBuilder(Protocol):
    def build(self, corpus_summary: str) -> ExtractionInstructionSet:
        """Build prompt instructions from raw corpus context before extraction."""


@dataclass(frozen=True)
class IngestionAgentSpec:
    name: str
    responsibility: str
    system_message: str


INGESTION_AGENT_SPECS = [
    IngestionAgentSpec(
        name="CorpusReaderAgent",
        responsibility="Read raw corpus and extract grounded business facts.",
        system_message=(
            "Read the banking corpus carefully and identify only grounded facts: "
            "customer intents, business events, rules, entities, process steps, documents, channels, and evidence."
        ),
    ),
    IngestionAgentSpec(
        name="FlowDesignerAgent",
        responsibility="Design complete business flows from grounded corpus evidence.",
        system_message=(
            "Propose candidate banking flows only when the corpus supports an end-to-end business process."
        ),
    ),
    IngestionAgentSpec(
        name="TaskDecomposerAgent",
        responsibility="Convert flow steps into reusable user tasks.",
        system_message="Convert candidate flow steps into reusable user_tasks.",
    ),
    IngestionAgentSpec(
        name="ActionExtractorAgent",
        responsibility="Separate frontend tools from backend tools.",
        system_message="Extract UI/channel events as frontend_tool and service/system/API operations as backend_tool.",
    ),
    IngestionAgentSpec(
        name="ConceptAgent",
        responsibility="Identify concepts and retrieval anchors.",
        system_message="Identify domain concepts, entities, products, events, and synonyms for retrieval.",
    ),
    IngestionAgentSpec(
        name="ValidatorAgent",
        responsibility="Challenge and validate the candidate extraction.",
        system_message="Reject unsupported inferred tools, missing references, and unsafe runtime assumptions.",
    ),
]


class RoleBasedExtractionInstructionBuilder:
    """Build deterministic role-based extraction instructions for local runs and tests."""

    def build(self, corpus_summary: str) -> ExtractionInstructionSet:
        return ExtractionInstructionSet(
            findings=[
                ExtractionInstruction(
                    agent="CorpusReaderAgent",
                    finding="Identify business events, customer intents, rules, entities, and reusable process steps from the raw corpus.",
                ),
                ExtractionInstruction(
                    agent="FlowDesignerAgent",
                    finding="Create complete business flows only when the corpus supports the process end to end.",
                ),
                ExtractionInstruction(
                    agent="TaskDecomposerAgent",
                    finding="Represent human or business steps as user_tasks and keep CRUD/API/calculation operations out of user_tasks.",
                ),
                ExtractionInstruction(
                    agent="ActionExtractorAgent",
                    finding="Separate UI-triggered frontend tools from service or system backend tools.",
                ),
                ExtractionInstruction(
                    agent="ConceptAgent",
                    finding="Attach domain concepts that explain why a flow matches future customer questions.",
                ),
                ExtractionInstruction(
                    agent="ValidatorAgent",
                    finding="Reject missing references, backend operations modeled as user tasks, and unsupported inferred tools.",
                ),
            ]
        )


@dataclass(frozen=True)
class IngestionOrchestratorConfig:
    raw_path: Path
    audit_directory: Path
    knowledge_base_service: KnowledgeBaseService | None = None
    clean: bool = False
    apply: bool = False
    extraction_instruction_mode: str = "none"
    max_validation_retries: int = 0
    require_human_review: bool = False
    semantic_analysis: bool = True


@dataclass(frozen=True)
class IngestionOrchestrationResult:
    """Run summary returned by the ingestion orchestrator."""

    mode: str
    audit_path: Path
    source_files: list[str]
    flows_persisted: int
    user_tasks_extracted: int
    tools_extracted: int
    steps: list[dict[str, Any]] = field(default_factory=list)
    extraction_result: dict[str, Any] = field(default_factory=dict)
    semantic_analysis_result: dict[str, Any] = field(default_factory=dict)
    extraction_instructions: dict[str, Any] = field(default_factory=dict)


class IngestionGraphState(TypedDict, total=False):
    config: IngestionOrchestratorConfig
    documents: list[CorpusDocument]
    extraction_instructions_context: str
    extraction_instructions: ExtractionInstructionSet
    extraction_result: dict[str, Any]
    semantic_analysis_result: SemanticAnalysisResult
    steps: list[dict[str, Any]]
    started_at: str
    audit_path: Path
    attempts: int
    error: str
    final_result: IngestionOrchestrationResult


@dataclass
class IngestionOrchestratorService:
    """LangGraph orchestrator for corpus ingestion.

    This is the single ingestion execution path. LangGraph owns the sequence,
    retry routing, failure branch, and the explicit instruction-building node.
    """

    loader: CorpusFlowLoader
    semantic_analyzer: SemanticAnalyzerService = field(
        default_factory=lambda: SemanticAnalyzerService(HeuristicSemanticAnalyzerProvider())
    )

    def run(self, config: IngestionOrchestratorConfig) -> IngestionOrchestrationResult:
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
        builder.add_node("analyze_semantics", self._analyze_semantics_node)
        builder.add_node("build_extraction_instructions", self._build_extraction_instructions_node)
        builder.add_node("extract_and_validate", self._extract_and_validate_node)
        builder.add_node("persist_knowledge", self._persist_knowledge_node)
        builder.add_node("write_audit", self._write_audit_node)
        builder.add_node("fail", self._fail_node)

        builder.add_edge(START, "scan_and_parse")
        builder.add_edge("scan_and_parse", "analyze_semantics")
        builder.add_edge("analyze_semantics", "build_extraction_instructions")
        builder.add_edge("build_extraction_instructions", "extract_and_validate")
        builder.add_conditional_edges(
            "extract_and_validate",
            self._route_after_extract,
            {
                "retry": "build_extraction_instructions",
                "write": "persist_knowledge",
                "fail": "fail",
            },
        )
        builder.add_edge("persist_knowledge", "write_audit")
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
        return {"documents": documents, "steps": steps}

    def _analyze_semantics_node(self, state: IngestionGraphState) -> dict[str, Any]:
        config = state["config"]
        steps = list(state.get("steps", []))
        semantic_analysis = self._analyze_semantics(config, state.get("documents", []), steps)
        return {"semantic_analysis_result": semantic_analysis, "steps": steps}

    def _build_extraction_instructions_node(self, state: IngestionGraphState) -> dict[str, Any]:
        config = state["config"]
        steps = list(state.get("steps", []))
        if self.loader.instruction_builder is None:
            self._record_step(
                steps,
                "build_extraction_instructions",
                self._owner_for_instruction_source(config.extraction_instruction_mode),
                "skipped",
                {"extraction_instruction_mode": config.extraction_instruction_mode},
            )
            return {"extraction_instructions_context": "", "extraction_instructions": ExtractionInstructionSet(), "steps": steps}

        extraction_instructions = self.loader.instruction_builder.build(
            self.loader.corpus_summary(state.get("documents", []))
        )
        extraction_instructions_context = extraction_instructions.to_prompt_context()
        self._record_step(
            steps,
            "build_extraction_instructions",
            self._owner_for_instruction_source(config.extraction_instruction_mode),
            "ok",
            {
                "extraction_instruction_mode": config.extraction_instruction_mode,
                "findings": len(extraction_instructions.findings),
            },
        )
        return {"extraction_instructions_context": extraction_instructions_context, "extraction_instructions": extraction_instructions, "steps": steps}

    def _extract_and_validate_node(self, state: IngestionGraphState) -> dict[str, Any]:
        config = state["config"]
        steps = list(state.get("steps", []))
        attempts = int(state.get("attempts", 0)) + 1
        semantic_analysis = state.get("semantic_analysis_result") or SemanticAnalysisResult()
        documents = self._documents_with_semantic_context(state.get("documents", []), semantic_analysis)
        try:
            result = self.loader.extract_documents(
                documents,
                extraction_instructions_context=state.get("extraction_instructions_context", ""),
            )
        except FlowExtractionError as exc:
            self._record_step(
                steps,
                "extract_validate_json",
                self._owner_for_instruction_source(config.extraction_instruction_mode),
                "retryable_error",
                {
                    "attempt": attempts,
                    "extraction_instruction_mode": config.extraction_instruction_mode,
                    "error": str(exc),
                },
            )
            return {"attempts": attempts, "steps": steps, "error": str(exc)}

        self._record_step(
            steps,
            "extract_validate_json",
            self._owner_for_instruction_source(config.extraction_instruction_mode),
            "ok",
            {
                "attempt": attempts,
                "extraction_instruction_mode": config.extraction_instruction_mode,
                "flows": len(result["flows"]),
                "user_tasks": len(result["user_tasks"]),
                "tools": len(result["tool_registry"]),
                "semantic_review_required": semantic_analysis.review_required,
            },
        )
        if semantic_analysis.classifications:
            result["semantic_analysis"] = semantic_analysis.to_dict()
        return {"attempts": attempts, "steps": steps, "error": "", "extraction_result": result}

    def _route_after_extract(self, state: IngestionGraphState) -> Literal["retry", "write", "fail"]:
        if not state.get("error"):
            return "write"
        config = state["config"]
        if int(state.get("attempts", 0)) <= config.max_validation_retries:
            return "retry"
        return "fail"

    def _persist_knowledge_node(self, state: IngestionGraphState) -> dict[str, Any]:
        config = state["config"]
        steps = list(state.get("steps", []))
        result = state["extraction_result"]
        records = self.loader.records_from_result(result)
        if config.knowledge_base_service is not None and config.apply:
            config.knowledge_base_service.ingest(records, clear=config.clean)
        self._record_step(
            steps,
            "persist_knowledge",
            "knowledge_base",
            "ok" if config.apply and config.knowledge_base_service is not None else "preview",
            {
                "mode": "apply" if config.apply else "preview",
                "requires_human_review": config.require_human_review or not config.apply,
                "records": len(records),
                "knowledge_base": type(config.knowledge_base_service.repository).__name__
                if config.knowledge_base_service is not None
                else None,
            },
        )
        return {"steps": steps}

    def _write_audit_node(self, state: IngestionGraphState) -> dict[str, Any]:
        config = state["config"]
        steps = list(state.get("steps", []))
        result = state["extraction_result"]
        semantic_analysis = state.get("semantic_analysis_result") or SemanticAnalysisResult()
        extraction_instructions = state.get("extraction_instructions") or ExtractionInstructionSet()
        audit_path = self._write_audit(
            config=config,
            documents=state.get("documents", []),
            result=result,
            steps=steps,
            started_at=state["started_at"],
            semantic_analysis=semantic_analysis,
            extraction_instructions=extraction_instructions,
        )
        self._record_step(
            steps,
            "write_audit",
            "langgraph",
            "ok",
            {"audit_path": str(audit_path)},
        )
        self._rewrite_audit_with_final_steps(audit_path, steps)
        final_result = IngestionOrchestrationResult(
            mode="apply" if config.apply else "preview",
            audit_path=audit_path,
            source_files=[str(doc.path) for doc in state.get("documents", [])],
            flows_persisted=len(result["flows"]) if config.apply and config.knowledge_base_service is not None else 0,
            user_tasks_extracted=len(result["user_tasks"]),
            tools_extracted=len(result["tool_registry"]),
            steps=steps,
            extraction_result=result,
            semantic_analysis_result=semantic_analysis.to_dict(),
            extraction_instructions=extraction_instructions.to_dict(),
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

    def _analyze_semantics(
        self,
        config: IngestionOrchestratorConfig,
        documents: list[CorpusDocument],
        steps: list[dict[str, Any]],
    ) -> SemanticAnalysisResult:
        if not config.semantic_analysis:
            return SemanticAnalysisResult()
        result = self.semantic_analyzer.analyze(documents)
        self._record_step(
            steps,
            "analyze_semantics_classify_corpus",
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
        config: IngestionOrchestratorConfig,
        documents: list[CorpusDocument],
        result: dict[str, Any],
        steps: list[dict[str, Any]],
        started_at: str,
        semantic_analysis: SemanticAnalysisResult,
        extraction_instructions: ExtractionInstructionSet,
    ) -> Path:
        config.audit_directory.mkdir(parents=True, exist_ok=True)
        audit_path = config.audit_directory / f"ingestion_run_{self._file_timestamp()}.json"
        review_required = config.require_human_review or semantic_analysis.review_required
        review_path = (
            self._write_human_review_artifact(
                config=config,
                semantic_analysis=semantic_analysis,
                result=result,
            )
            if review_required
            else None
        )
        payload = {
            "started_at": started_at,
            "finished_at": self._now(),
            "mode": "apply" if config.apply else "preview",
            "extraction_instruction_mode": config.extraction_instruction_mode,
            "semantic_analysis": semantic_analysis.to_dict(),
            "extraction_instructions": extraction_instructions.to_dict(),
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
                "knowledge_base": type(config.knowledge_base_service.repository).__name__
                if config.knowledge_base_service is not None
                else None,
                "applied": config.apply and config.knowledge_base_service is not None,
                "flows": [flow["flow_id"] for flow in result["flows"]],
                "user_tasks": [task["user_task_id"] for task in result["user_tasks"]],
                "tools": [tool["tool_id"] for tool in result["tool_registry"]],
            },
            "steps": steps,
        }
        audit_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return audit_path

    def _write_human_review_artifact(
        self,
        config: IngestionOrchestratorConfig,
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
                "tools": [tool.get("tool_id") for tool in result.get("tool_registry", [])],
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

    def _owner_for_instruction_source(self, extraction_instruction_mode: str) -> str:
        if extraction_instruction_mode == "role_based":
            return "role_based_ingestion_agents"
        return "llm_extraction_plus_custom_validation"

    def _optional_import(self, module_name: str, friendly_name: str):
        try:
            return import_module(module_name)
        except ImportError as exc:
            raise RuntimeError(
                f"Optional dependency '{friendly_name}' is required for ingestion orchestration."
            ) from exc

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _file_timestamp(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
