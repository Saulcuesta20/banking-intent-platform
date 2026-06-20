from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from importlib import import_module
from pathlib import Path
from typing import Any, Literal, Protocol, TypedDict

from app.config.model import load_asset_payload_composition
from app.config.settings import load_settings
from app.ingestion.asset_pipeline import CanonicalAssetPipeline
from app.ingestion.llm_flow_loader import CorpusDocument, CorpusFlowLoader, FlowExtractionError
from app.ingestion.semantic_analyzer import (
    HeuristicSemanticAnalyzerProvider,
    SemanticAnalysisResult,
    SemanticAnalyzerService,
)
from app.ingestion.staging import IngestionAssetSetStager, StagedAssetSet
from app.knowledge_base.asset_sets import AssetSetDeploymentService
from app.knowledge_base.catalog_store import AssetCatalogStore
from app.knowledge_base.models import EnterpriseAsset
from app.knowledge_base.registry import EnterpriseAssetRegistry
from app.knowledge_base.service import KnowledgeBaseService


INGESTION_ASSET_TYPES = [
    "semantic_space",
    "domain",
    "module",
    "menu",
    "form",
    "form_version",
    "flow",
    "process",
    "qa",
    "plan",
    "user_task",
    "business_rule",
    "ruleset",
    "concept",
    "entity",
    "tool",
    "document",
    "configuration",
    "asset_set",
    "causality",
]


DEFAULT_PAYLOAD_COMPOSITION_BY_ASSET_TYPE: dict[str, list[str]] = {
    "semantic_space": ["semantic_space_id", "name", "route_hints", "structural_layers", "allowed_asset_types", "retrieval_policy", "entities"],
    "domain": ["domain_id", "label", "description", "order"],
    "module": ["module_id", "domain_id", "label", "description", "menus"],
    "menu": ["menu_id", "module_id", "label", "path", "children"],
    "form": ["form_id", "module_id", "fields", "layout", "validation"],
    "form_version": ["form_id", "version", "schema", "renderer", "bindings"],
    "flow": ["flow_id", "flow_name", "intent", "business_event", "user_tasks", "related_process_ids"],
    "process": ["process_id", "nodes", "edges", "decisions", "systems", "exceptions"],
    "qa": ["question", "answer", "intent", "source", "citations"],
    "plan": ["plan_id", "steps", "tools", "dependencies", "execution_options"],
    "user_task": ["user_task_id", "task", "type", "name", "description", "user_actions", "tools"],
    "business_rule": ["rule_id", "rule_text", "conditions", "consequences", "applies_to"],
    "ruleset": ["ruleset_id", "rules", "transaction_id", "entities", "scope"],
    "concept": ["concept_id", "name", "aliases", "definition", "relations"],
    "entity": ["entity_id", "name", "aliases", "structural_layer", "subtype", "attributes", "relations", "evidence"],
    "tool": ["tool_id", "tool_type", "operation", "resource", "label", "endpoint"],
    "document": ["document_id", "title", "source", "content", "citations"],
    "configuration": ["config_id", "scope", "settings", "environment", "owner"],
    "asset_set": ["asset_set_id", "version", "members", "status", "metadata"],
    "causality": ["cause_text", "effect_text", "relation_kind", "evidence", "targets"],
}


def _payload_composition_by_asset_type() -> dict[str, list[str]]:
    configured = load_asset_payload_composition()
    return {
        **DEFAULT_PAYLOAD_COMPOSITION_BY_ASSET_TYPE,
        **{asset_type: fields for asset_type, fields in configured.items() if fields},
    }


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
    asset_catalog_store: AssetCatalogStore | None = None
    asset_registry: EnterpriseAssetRegistry | None = None
    asset_staging_directory: Path | None = None
    clean: bool = False
    apply: bool = False
    project_knowledge_bases: bool = True
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
    canonical_assets_generated: int = 0
    catalog_assets_persisted: int = 0
    staged_asset_sets: list[dict[str, Any]] = field(default_factory=list)
    steps: list[dict[str, Any]] = field(default_factory=list)
    extraction_result: dict[str, Any] = field(default_factory=dict)
    semantic_analysis_result: dict[str, Any] = field(default_factory=dict)
    extraction_instructions: dict[str, Any] = field(default_factory=dict)
    asset_analysis: dict[str, Any] = field(default_factory=dict)
    knowledge_base_error: str | None = None


class IngestionGraphState(TypedDict, total=False):
    config: IngestionOrchestratorConfig
    documents: list[CorpusDocument]
    domain_analysis: dict[str, Any]
    extraction_instructions_context: str
    extraction_instructions: ExtractionInstructionSet
    extraction_result: dict[str, Any]
    canonical_assets: list[EnterpriseAsset]
    staged_asset_sets: list[StagedAssetSet]
    asset_analysis: dict[str, Any]
    semantic_analysis_result: SemanticAnalysisResult
    steps: list[dict[str, Any]]
    started_at: str
    audit_path: Path
    attempts: int
    error: str
    catalog_assets_persisted: int
    knowledge_base_error: str
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
    canonical_asset_pipeline: CanonicalAssetPipeline | None = None

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
        builder.add_node("analyze_domain", self._analyze_domain_node)
        builder.add_node("analyze_semantics", self._analyze_semantics_node)
        builder.add_node("build_extraction_instructions", self._build_extraction_instructions_node)
        builder.add_node("extract_and_validate", self._extract_and_validate_node)
        builder.add_node("classify_asset_types", self._classify_asset_types_node)
        builder.add_node("resolve_aliases_and_similarity", self._resolve_aliases_and_similarity_node)
        builder.add_node("hydrate_asset_payloads", self._hydrate_asset_payloads_node)
        builder.add_node("normalize_asset_relationships", self._normalize_asset_relationships_node)
        builder.add_node("generate_canonical_assets", self._generate_canonical_assets_node)
        builder.add_node("validate_and_review", self._validate_and_review_node)
        builder.add_node("stage_asset_set_yaml", self._stage_asset_set_yaml_node)
        builder.add_node("persist_catalog", self._persist_catalog_node)
        builder.add_node("prepare_human_review_actions", self._prepare_human_review_actions_node)
        builder.add_node("persist_knowledge", self._persist_knowledge_node)
        builder.add_node("write_audit", self._write_audit_node)
        builder.add_node("fail", self._fail_node)

        builder.add_edge(START, "scan_and_parse")
        builder.add_edge("scan_and_parse", "analyze_domain")
        builder.add_edge("analyze_domain", "analyze_semantics")
        builder.add_edge("analyze_semantics", "build_extraction_instructions")
        builder.add_edge("build_extraction_instructions", "extract_and_validate")
        builder.add_conditional_edges(
            "extract_and_validate",
            self._route_after_extract,
            {
                "retry": "build_extraction_instructions",
                "write": "classify_asset_types",
                "fail": "fail",
            },
        )
        builder.add_edge("classify_asset_types", "resolve_aliases_and_similarity")
        builder.add_edge("resolve_aliases_and_similarity", "hydrate_asset_payloads")
        builder.add_edge("hydrate_asset_payloads", "normalize_asset_relationships")
        builder.add_edge("normalize_asset_relationships", "generate_canonical_assets")
        builder.add_edge("generate_canonical_assets", "validate_and_review")
        builder.add_edge("validate_and_review", "persist_catalog")
        builder.add_edge("persist_catalog", "stage_asset_set_yaml")
        builder.add_edge("stage_asset_set_yaml", "prepare_human_review_actions")
        builder.add_edge("prepare_human_review_actions", "persist_knowledge")
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

    def _analyze_domain_node(self, state: IngestionGraphState) -> dict[str, Any]:
        """Fase 0: Analyze corpus to identify business domain and ask one clarifying question."""
        config = state["config"]
        steps = list(state.get("steps", []))
        documents = state.get("documents", [])

        # Analyze corpus to identify domain
        domain_analysis = self._analyze_corpus_domain(documents)

        # Store domain analysis in state for later use
        domain_info = {
            "identified_domain": domain_analysis.get("domain", "unknown"),
            "confidence": domain_analysis.get("confidence", 0.0),
            "key_entities": domain_analysis.get("key_entities", []),
            "question_asked": domain_analysis.get("question", None),
            "user_answer": None,  # Will be filled by CLI interaction
        }

        self._record_step(
            steps,
            "analyze_domain_fase0",
            "domain_analysis",
            "ok",
            {
                "identified_domain": domain_info["identified_domain"],
                "confidence": domain_info["confidence"],
                "key_entities_count": len(domain_info["key_entities"]),
                "question": domain_info["question_asked"],
            },
        )
        return {"domain_analysis": domain_info, "steps": steps}

    def _analyze_corpus_domain(self, documents: list[CorpusDocument]) -> dict[str, Any]:
        """Analyze corpus to identify the business domain."""
        # Combine all document texts for analysis
        combined_text = "\n".join([doc.text for doc in documents if doc.text])[:5000]

        # Simple heuristic domain detection
        domain_keywords = {
            "banking": ["bank", "loan", "account", "credit", "debit", "transfer", "payment"],
            "insurance": ["insurance", "policy", "premium", "claim", "coverage", "deductible"],
            "healthcare": ["patient", "medical", "hospital", "diagnosis", "treatment", "health"],
            "retail": ["product", "inventory", "order", "shipping", "customer", "purchase"],
            "manufacturing": ["production", "assembly", "quality", "supply", "warehouse", "batch"],
        }

        detected_domain = "unknown"
        max_score = 0
        key_entities = []

        for domain, keywords in domain_keywords.items():
            score = sum(1 for kw in keywords if kw.lower() in combined_text.lower())
            if score > max_score:
                max_score = score
                detected_domain = domain
                # Extract some entities from the domain
                key_entities = [kw for kw in keywords if kw.lower() in combined_text.lower()][:5]

        confidence = min(max_score / 5.0, 1.0)  # Normalize to 0-1

        # Generate a clarifying question based on domain
        question = None
        if detected_domain != "unknown":
            question = f"I detected this is about {detected_domain}. Can you confirm this is correct?"

        return {
            "domain": detected_domain,
            "confidence": confidence,
            "key_entities": key_entities,
            "question": question,
        }

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
                "asset_arrays": {
                    key: len(value)
                    for key, value in result.items()
                    if isinstance(value, list) and key != "tool_registry"
                },
                "semantic_review_required": semantic_analysis.review_required,
            },
        )
        if semantic_analysis.classifications:
            result["semantic_analysis"] = semantic_analysis.to_dict()
        return {"attempts": attempts, "steps": steps, "error": "", "extraction_result": result}

    def _classify_asset_types_node(self, state: IngestionGraphState) -> dict[str, Any]:
        steps = list(state.get("steps", []))
        result = state["extraction_result"]
        semantic_analysis = state.get("semantic_analysis_result") or SemanticAnalysisResult()
        asset_analysis = {
            "asset_types": self._asset_type_classification(result, semantic_analysis),
            "aliases": [],
            "payloads": {},
            "relationships": [],
            "human_review_actions": [],
        }
        discovered = {
            asset_type: summary["candidate_count"]
            for asset_type, summary in asset_analysis["asset_types"].items()
            if summary["candidate_count"]
        }
        self._record_step(
            steps,
            "classify_asset_types",
            "langgraph_asset_classifier",
            "ok",
            {
                "supported_asset_types": len(INGESTION_ASSET_TYPES),
                "discovered_asset_types": discovered,
                "note": "Flow extraction is only the first asset source; missing asset types remain explicit review candidates.",
            },
        )
        return {"asset_analysis": asset_analysis, "steps": steps}

    def _resolve_aliases_and_similarity_node(self, state: IngestionGraphState) -> dict[str, Any]:
        steps = list(state.get("steps", []))
        result = state["extraction_result"]
        asset_analysis = dict(state.get("asset_analysis") or {})
        aliases = self._alias_candidates(result)
        asset_analysis["aliases"] = aliases
        self._record_step(
            steps,
            "resolve_aliases_and_similarity",
            "vector_memory_or_human_review",
            "candidate",
            {
                "alias_candidates": len(aliases),
                "coverage": sorted({item["asset_type"] for item in aliases}),
                "note": "Alias candidates are reviewable until full vector similarity is applied to every asset type.",
            },
        )
        return {"asset_analysis": asset_analysis, "steps": steps}

    def _hydrate_asset_payloads_node(self, state: IngestionGraphState) -> dict[str, Any]:
        steps = list(state.get("steps", []))
        result = state["extraction_result"]
        asset_analysis = dict(state.get("asset_analysis") or {})
        payloads = self._payload_hydration_plan(result)
        asset_analysis["payloads"] = payloads
        incomplete = [
            asset_type
            for asset_type, summary in payloads.items()
            if summary["status"] != "candidate_payload_available"
        ]
        self._record_step(
            steps,
            "hydrate_asset_payloads",
            "asset_schema_hydration",
            "candidate",
            {
                "payload_asset_types": len(payloads),
                "incomplete_asset_types": incomplete,
                "note": "Every asset type has an expected payload composition, even when extraction did not produce candidates yet.",
            },
        )
        return {"asset_analysis": asset_analysis, "steps": steps}

    def _normalize_asset_relationships_node(self, state: IngestionGraphState) -> dict[str, Any]:
        steps = list(state.get("steps", []))
        result = state["extraction_result"]
        asset_analysis = dict(state.get("asset_analysis") or {})
        relationships = self._relationship_candidates(result)
        asset_analysis["relationships"] = relationships
        self._record_step(
            steps,
            "normalize_asset_relationships",
            "relationship_normalization",
            "candidate",
            {
                "relationship_candidates": len(relationships),
                "relationship_types": sorted({item["type"] for item in relationships}),
                "note": "Relationships are part of ingestion analysis and must be reviewed before governed AssetSet activation.",
            },
        )
        return {"asset_analysis": asset_analysis, "steps": steps}

    def _generate_canonical_assets_node(self, state: IngestionGraphState) -> dict[str, Any]:
        steps = list(state.get("steps", []))
        asset_analysis = dict(state.get("asset_analysis") or {})
        if self.canonical_asset_pipeline is None:
            self._record_step(
                steps,
                "generate_canonical_assets",
                "canonical_asset_pipeline",
                "skipped",
                {"reason": "canonical asset pipeline is not configured"},
            )
            return {"canonical_assets": [], "asset_analysis": asset_analysis, "steps": steps}

        result = state["extraction_result"]
        records = self.loader.records_from_result(result)
        assets = self.canonical_asset_pipeline.run(
            documents=state.get("documents", []),
            extraction=result,
            records=records,
        )
        by_type: dict[str, int] = {}
        for asset in assets:
            by_type[asset.asset_type] = by_type.get(asset.asset_type, 0) + 1
        asset_analysis["canonical_assets"] = {
            "candidate_count": len(assets),
            "asset_types": by_type,
            "asset_ids": [asset.asset_id for asset in assets],
        }
        self._record_step(
            steps,
            "generate_canonical_assets",
            "canonical_asset_pipeline",
            "candidate",
            {
                "canonical_assets": len(assets),
                "asset_types": by_type,
                "note": "Canonical assets are generated for review/catalog persistence before governed deployment.",
            },
        )
        return {"canonical_assets": assets, "asset_analysis": asset_analysis, "steps": steps}

    def _validate_and_review_node(self, state: IngestionGraphState) -> dict[str, Any]:
        """Fase 4: Validate extracted assets and ask one review question."""
        steps = list(state.get("steps", []))
        config = state["config"]
        canonical_assets = state.get("canonical_assets", [])
        asset_analysis = dict(state.get("asset_analysis") or {})

        # Analyze extracted assets for quality
        validation_result = self._validate_extracted_assets(canonical_assets)

        # Generate review question
        review_question = None
        if validation_result.get("issues"):
            issues_summary = "; ".join(validation_result["issues"][:3])
            review_question = f"I found some issues with the extracted assets: {issues_summary}. Should I proceed with these or would you like to review them first?"

        # Store validation results
        asset_analysis["validation"] = {
            "total_assets": len(canonical_assets),
            "asset_types": validation_result.get("asset_type_counts", {}),
            "issues": validation_result.get("issues", []),
            "quality_score": validation_result.get("quality_score", 0.0),
            "review_question": review_question,
        }

        self._record_step(
            steps,
            "validate_and_review_fase4",
            "asset_validation",
            "ok",
            {
                "total_assets": len(canonical_assets),
                "issues_found": len(validation_result.get("issues", [])),
                "quality_score": validation_result.get("quality_score", 0.0),
                "review_question": review_question,
            },
        )
        return {"asset_analysis": asset_analysis, "steps": steps}

    def _validate_extracted_assets(self, assets: list[EnterpriseAsset]) -> dict[str, Any]:
        """Validate extracted assets for quality and completeness."""
        issues = []
        asset_type_counts = {}

        for asset in assets:
            # Count by type
            asset_type_counts[asset.asset_type] = asset_type_counts.get(asset.asset_type, 0) + 1

            # Check for missing descriptions
            if not asset.description or len(asset.description) < 10:
                issues.append(f"Asset '{asset.name}' has missing or too short description")

            # Check for empty payloads
            if not asset.payload:
                issues.append(f"Asset '{asset.name}' has empty payload")

            # Check for entities without structural layer.
            if asset.asset_type == "entity" and not (asset.structural_layer or asset.business_layer):
                issues.append(f"Entity '{asset.name}' is missing structural_layer classification")

        # Calculate quality score
        total_assets = len(assets)
        issues_count = len(issues)
        quality_score = max(0.0, 1.0 - (issues_count / max(total_assets, 1)))

        return {
            "asset_type_counts": asset_type_counts,
            "issues": issues,
            "quality_score": quality_score,
        }

    def _stage_asset_set_yaml_node(self, state: IngestionGraphState) -> dict[str, Any]:
        steps = list(state.get("steps", []))
        config = state["config"]
        asset_analysis = dict(state.get("asset_analysis") or {})
        assets = state.get("canonical_assets", [])
        if not assets:
            self._record_step(
                steps,
                "stage_asset_set_yaml",
                "ingestion_asset_set_stager",
                "skipped",
                {"reason": "no canonical assets generated"},
            )
            return {"staged_asset_sets": [], "asset_analysis": asset_analysis, "steps": steps}

        staging_root = config.asset_staging_directory or (
            load_settings().project_root / "app" / "assets" / "staging" / "ingest-runs"
        )
        run_id = self._run_id(state["started_at"])
        staged = IngestionAssetSetStager(staging_root).write_run(
            run_id=run_id,
            assets=assets,
            version="1.0.0",
        )
        asset_analysis["staged_asset_sets"] = [item.to_dict() for item in staged]
        self._record_step(
            steps,
            "stage_asset_set_yaml",
            "ingestion_asset_set_stager",
            "ok",
            {
                "run_id": run_id,
                "staged_asset_sets": len(staged),
                "manifest_paths": [str(item.manifest_path) for item in staged],
            "note": "Canonical ingestion assets are written as governed AssetSet YAML proposals.",
        },
    )
        return {"staged_asset_sets": staged, "asset_analysis": asset_analysis, "steps": steps}

    def _persist_catalog_node(self, state: IngestionGraphState) -> dict[str, Any]:
        config = state["config"]
        steps = list(state.get("steps", []))
        canonical_assets = state.get("canonical_assets", [])
        catalog_assets_persisted = 0

        if config.asset_catalog_store is not None and config.asset_registry is not None and config.apply:
            from app.events import emit_asset_status_change
            config.asset_catalog_store.initialize(clear=config.clean)
            for asset in canonical_assets:
                config.asset_catalog_store.upsert_asset(asset, config.asset_registry)
                emit_asset_status_change(
                    asset.asset_id, asset.asset_type, "draft", "draft",
                    version=asset.version, source="ingestion",
                )
                catalog_assets_persisted += 1

        self._record_step(
            steps,
            "persist_catalog",
            "asset_catalog",
            "ok" if catalog_assets_persisted or not config.apply else "preview",
            {
                "mode": "apply" if config.apply else "preview",
                "catalog_assets_persisted": catalog_assets_persisted,
                "canonical_assets": len(canonical_assets),
                "note": "Catalog assets are written early so the launcher can see them before the KB projection tail finishes.",
            },
        )
        return {"catalog_assets_persisted": catalog_assets_persisted, "steps": steps}

    def _prepare_human_review_actions_node(self, state: IngestionGraphState) -> dict[str, Any]:
        steps = list(state.get("steps", []))
        config = state["config"]
        asset_analysis = dict(state.get("asset_analysis") or {})
        review_actions = self._human_review_actions(asset_analysis)
        asset_analysis["human_review_actions"] = review_actions
        self._record_step(
            steps,
            "prepare_human_review_actions",
            "human_review",
            "required" if config.require_human_review or review_actions else "not_required",
            {
                "actions": len(review_actions),
                "action_types": sorted({item["action_type"] for item in review_actions}),
                "note": "Human review covers actions, tools, entities, services, payloads, aliases, and relationships.",
            },
        )
        return {"asset_analysis": asset_analysis, "steps": steps}

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
        asset_analysis = state.get("asset_analysis") or {}
        canonical_assets = state.get("canonical_assets", [])
        staged_asset_sets = state.get("staged_asset_sets", [])
        records = self.loader.records_from_result(result)
        catalog_asset_sets_persisted = 0
        knowledge_base_error = ""
        if config.asset_catalog_store is not None and config.asset_registry is not None and config.apply and staged_asset_sets and config.project_knowledge_bases:
            from app.config.settings import load_settings as _load_settings
            from app.knowledge_base.adapters.document.sqlite import SQLiteDocumentKnowledgeBaseAdapter
            from app.knowledge_base.adapters.vector.qdrant import QdrantKnowledgeBaseVectorAdapter
            _settings = _load_settings()
            _graph_adapter = config.knowledge_base_service.repository if config.knowledge_base_service is not None else None
            deployment = AssetSetDeploymentService(
                store=config.asset_catalog_store,
                registry=config.asset_registry,
                graph=_graph_adapter,
                vector=QdrantKnowledgeBaseVectorAdapter(_settings.qdrant_host, _settings.qdrant_api_key),
                document=SQLiteDocumentKnowledgeBaseAdapter(_settings.processed_directory / "knowledge_base" / "document_kb.sqlite"),
            )
            for staged in staged_asset_sets:
                try:
                    load_result = deployment.load(
                        staged.manifest_path,
                        actor="ingestion",
                        comment="Ingestion generated AssetSet YAML proposal.",
                    )
                    catalog_asset_sets_persisted += 1
                except Exception as exc:
                    import logging
                    logging.warning("Skipping staged set %s: %s", staged.asset_set_id, exc)
                    continue
                asset_set_id = staged.asset_set_id
                asset_set_version = staged.version
                asset_set = config.asset_catalog_store.get_asset_set(asset_set_id, asset_set_version)
                if asset_set is not None:
                    try:
                        deployment._project(asset_set)
                    except Exception:
                        pass
        if config.knowledge_base_service is not None and config.apply and config.project_knowledge_bases:
            try:
                config.knowledge_base_service.repository.initialize()
            except Exception as exc:  # pragma: no cover - external KB failures are environment-dependent
                knowledge_base_error = str(exc)
        self._record_step(
            steps,
            "persist_knowledge",
            "knowledge_base" if not knowledge_base_error else "knowledge_base_partial",
            "ok"
            if config.apply and (config.knowledge_base_service is not None or int(state.get("catalog_assets_persisted", 0))) and not knowledge_base_error
            else ("warning" if knowledge_base_error else "preview"),
            {
                "mode": "apply" if config.apply else "preview",
                "requires_human_review": config.require_human_review or not config.apply,
                "records": len(records),
                "canonical_assets": len(canonical_assets),
                "staged_asset_sets": len(staged_asset_sets),
                "catalog_asset_sets_persisted": catalog_asset_sets_persisted,
                "catalog_assets_persisted": int(state.get("catalog_assets_persisted", 0)),
                "knowledge_base_error": knowledge_base_error or None,
                "asset_types_reviewed": len(asset_analysis.get("asset_types") or {}),
                "knowledge_base": type(config.knowledge_base_service.repository).__name__
                if config.knowledge_base_service is not None
                else None,
                "project_knowledge_bases": config.project_knowledge_bases,
            },
        )
        return {
            "steps": steps,
            "knowledge_base_error": knowledge_base_error,
        }

    def _write_audit_node(self, state: IngestionGraphState) -> dict[str, Any]:
        config = state["config"]
        steps = list(state.get("steps", []))
        result = state["extraction_result"]
        asset_analysis = state.get("asset_analysis") or {}
        canonical_assets = state.get("canonical_assets", [])
        staged_asset_sets = state.get("staged_asset_sets", [])
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
            asset_analysis=asset_analysis,
            canonical_assets=canonical_assets,
            staged_asset_sets=staged_asset_sets,
            catalog_assets_persisted=int(state.get("catalog_assets_persisted", 0)),
            knowledge_base_error=str(state.get("knowledge_base_error") or ""),
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
            canonical_assets_generated=len(state.get("canonical_assets", [])),
            catalog_assets_persisted=int(state.get("catalog_assets_persisted", 0)),
            staged_asset_sets=[item.to_dict() for item in staged_asset_sets],
            steps=steps,
            extraction_result=result,
            semantic_analysis_result=semantic_analysis.to_dict(),
            extraction_instructions=extraction_instructions.to_dict(),
            asset_analysis=asset_analysis,
            knowledge_base_error=state.get("knowledge_base_error") or None,
        )
        return {
            "steps": steps,
            "audit_path": audit_path,
            "final_result": final_result,
            "knowledge_base_error": state.get("knowledge_base_error") or "",
        }

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
        asset_analysis: dict[str, Any],
        canonical_assets: list[EnterpriseAsset],
        staged_asset_sets: list[StagedAssetSet],
        catalog_assets_persisted: int,
        knowledge_base_error: str,
    ) -> Path:
        config.audit_directory.mkdir(parents=True, exist_ok=True)
        audit_path = config.audit_directory / f"ingestion_run_{self._file_timestamp()}.json"
        review_required = (
            config.require_human_review
            or semantic_analysis.review_required
            or bool(asset_analysis.get("human_review_actions"))
        )
        review_path = (
            self._write_human_review_artifact(
                config=config,
                semantic_analysis=semantic_analysis,
                result=result,
                asset_analysis=asset_analysis,
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
                "applied": config.apply
                and (config.knowledge_base_service is not None or catalog_assets_persisted > 0),
                "flows": [flow["flow_id"] for flow in result["flows"]],
                "user_tasks": [task["user_task_id"] for task in result["user_tasks"]],
                "tools": [tool["tool_id"] for tool in result["tool_registry"]],
                "canonical_assets": [asset.asset_id for asset in canonical_assets],
                "staged_asset_sets": [item.to_dict() for item in staged_asset_sets],
                "catalog_assets_persisted": catalog_assets_persisted,
                "knowledge_base_error": knowledge_base_error or None,
                "asset_analysis": asset_analysis,
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
        asset_analysis: dict[str, Any] | None = None,
    ) -> Path:
        review_directory = config.audit_directory / "human_review"
        review_directory.mkdir(parents=True, exist_ok=True)
        review_path = review_directory / f"ingestion_review_{self._file_timestamp()}.json"
        payload = {
            "status": "pending",
            "instructions": self._human_review_instructions(),
            "reviewer_notes": "",
            "semantic_analysis": semantic_analysis.to_dict(),
            "asset_analysis": asset_analysis or {},
            "candidate_outputs": {
                "flows": [flow.get("flow_id") for flow in result.get("flows", [])],
                "user_tasks": [task.get("user_task_id") for task in result.get("user_tasks", [])],
                "tools": [tool.get("tool_id") for tool in result.get("tool_registry", [])],
            },
        }
        review_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return review_path

    def _asset_type_classification(
        self,
        result: dict[str, Any],
        semantic_analysis: SemanticAnalysisResult,
    ) -> dict[str, dict[str, Any]]:
        payload_composition = _payload_composition_by_asset_type()
        flow_count = len(result.get("flows", []))
        user_task_count = len(result.get("user_tasks", []))
        tool_count = len(result.get("tool_registry", []))
        knowledge_types = [
            knowledge_type
            for classification in semantic_analysis.classifications
            for knowledge_type in classification.knowledge_types
        ]
        type_counts = {asset_type: 0 for asset_type in INGESTION_ASSET_TYPES}
        type_counts.update(
            {
                "flow": flow_count,
                "user_task": user_task_count,
                "tool": tool_count,
                "entity": len(self._concept_names(result)),
                "concept": len(self._concept_names(result)),
                "business_rule": knowledge_types.count("rule"),
                "document": knowledge_types.count("document"),
                "process": len({process for classification in semantic_analysis.classifications for process in classification.processes}),
            }
        )
        for asset_type in INGESTION_ASSET_TYPES:
            extracted_count = len(result.get(asset_type, [])) if isinstance(result.get(asset_type), list) else 0
            if extracted_count:
                type_counts[asset_type] = extracted_count
        if type_counts.get("entity"):
            type_counts["concept"] = max(type_counts.get("concept", 0), type_counts["entity"])
        return {
            asset_type: {
                "candidate_count": type_counts.get(asset_type, 0),
                "status": "candidate_detected" if type_counts.get(asset_type, 0) else "not_detected_yet",
                "payload_fields": payload_composition.get(asset_type, []),
            }
            for asset_type in INGESTION_ASSET_TYPES
        }

    def _alias_candidates(self, result: dict[str, Any]) -> list[dict[str, Any]]:
        aliases: list[dict[str, Any]] = []
        for flow in result.get("flows", []):
            flow_id = str(flow.get("flow_id") or "")
            if flow_id:
                aliases.append(
                    {
                        "asset_type": "flow",
                        "asset_id": f"flow.{flow_id}",
                        "aliases": self._dedupe_texts(
                            [
                                flow.get("flow_name"),
                                flow.get("purpose"),
                                flow.get("intent"),
                                *(flow.get("utterances") or []),
                            ]
                        ),
                        "source": "flow_name_purpose_legacy_intent_utterances",
                    }
                )
            for concept, values in (flow.get("concept_aliases") or {}).items():
                aliases.append(
                    {
                        "asset_type": "entity",
                        "asset_id": f"entity.{self._slug(concept)}",
                        "aliases": self._dedupe_texts([concept, *values]),
                        "source": "flow_concept_aliases",
                    }
                )
        for tool in result.get("tool_registry", []):
            tool_id = str(tool.get("tool_id") or "")
            if tool_id:
                aliases.append(
                    {
                        "asset_type": "tool",
                        "asset_id": f"tool.{tool_id}",
                        "aliases": self._dedupe_texts([tool.get("label"), tool_id, tool.get("operation")]),
                        "source": "tool_registry",
                    }
                )
        return aliases

    def _payload_hydration_plan(self, result: dict[str, Any]) -> dict[str, dict[str, Any]]:
        payload_composition = _payload_composition_by_asset_type()
        available = {
            "flow": len(result.get("flows", [])),
            "user_task": len(result.get("user_tasks", [])),
            "tool": len(result.get("tool_registry", [])),
            "entity": len(self._concept_names(result)),
            "concept": len(self._concept_names(result)),
        }
        for asset_type in INGESTION_ASSET_TYPES:
            extracted_count = len(result.get(asset_type, [])) if isinstance(result.get(asset_type), list) else 0
            if extracted_count:
                available[asset_type] = extracted_count
        if available.get("entity"):
            available["concept"] = max(available.get("concept", 0), available["entity"])
        return {
            asset_type: {
                "expected_fields": fields,
                "candidate_count": available.get(asset_type, 0),
                "status": "candidate_payload_available" if available.get(asset_type, 0) else "schema_defined_no_candidate",
            }
            for asset_type, fields in payload_composition.items()
        }

    def _relationship_candidates(self, result: dict[str, Any]) -> list[dict[str, str]]:
        relationships: list[dict[str, str]] = []
        for module in result.get("module", []) or []:
            if module.get("module_id") and module.get("domain_id"):
                relationships.append(
                    {
                        "source_asset_id": f"module.{self._slug(module['module_id'])}",
                        "type": "belongs_to_domain",
                        "target_asset_id": f"domain.{self._slug(module['domain_id'])}",
                    }
                )
        for asset_type in ("menu", "form"):
            for item in result.get(asset_type, []) or []:
                item_id = item.get(f"{asset_type}_id") or item.get("id")
                if item_id and item.get("module_id"):
                    relationships.append(
                        {
                            "source_asset_id": f"{asset_type}.{self._slug(item_id)}",
                            "type": "belongs_to_module",
                            "target_asset_id": f"module.{self._slug(item['module_id'])}",
                        }
                    )
        for form_version in result.get("form_version", []) or []:
            if form_version.get("form_id"):
                relationships.append(
                    {
                        "source_asset_id": f"form_version.{self._slug(form_version['form_id'])}.{self._slug(form_version.get('version', 'v1'))}",
                        "type": "version_of",
                        "target_asset_id": f"form.{self._slug(form_version['form_id'])}",
                    }
                )
        relation_by_member_type = {
            "flow": "groups_flow",
            "process": "groups_process",
            "plan": "groups_plan",
            "ruleset": "groups_ruleset",
            "business_rule": "groups_rule",
            "entity": "groups_entity",
            "tool": "groups_tool",
            "qa": "groups_qa",
            "causality": "groups_causality",
            "user_task": "groups_user_task",
        }
        for asset_set in result.get("asset_set", []) or []:
            asset_set_id = asset_set.get("asset_set_id") or asset_set.get("id")
            if not asset_set_id:
                continue
            for member in asset_set.get("members") or []:
                member_id = str(member.get("asset_id") if isinstance(member, dict) else member).strip()
                member_type = str(member.get("asset_type") if isinstance(member, dict) else member_id.split(".", 1)[0]).strip()
                relation_type = relation_by_member_type.get(member_type)
                if relation_type and member_id:
                    relationships.append(
                        {
                            "source_asset_id": f"asset_set.{self._slug(asset_set_id)}",
                            "type": relation_type,
                            "target_asset_id": member_id,
                        }
                    )
        tasks_by_id = {str(task.get("user_task_id")): task for task in result.get("user_tasks", [])}
        task_id_to_asset_id: dict[str, str] = {}
        for task in result.get("user_tasks", []):
            ut_id = str(task.get("user_task_id") or "")
            if ut_id:
                task_id_to_asset_id[ut_id] = f"user_task.{self._slug(task.get('name') or ut_id)}"
        for flow in result.get("flows", []):
            flow_asset_id = f"flow.{flow.get('flow_id')}"
            for task_ref in flow.get("user_task_refs") or []:
                target_id = task_id_to_asset_id.get(str(task_ref)) or f"user_task.{task_ref}"
                relationships.append(
                    {
                        "source_asset_id": flow_asset_id,
                        "type": "decomposes_to_user_task",
                        "target_asset_id": target_id,
                    }
                )
                task = tasks_by_id.get(str(task_ref)) or {}
                for tool in task.get("tools") or []:
                    if tool.get("tool_id"):
                        relationships.append(
                            {
                                "source_asset_id": target_id,
                                "type": "invokes_tool",
                                "target_asset_id": f"tool.{tool['tool_id']}",
                            }
                        )
            for concept in flow.get("concepts") or []:
                relationships.append(
                    {
                        "source_asset_id": flow_asset_id,
                        "type": "uses_concept",
                        "target_asset_id": f"entity.{self._slug(concept)}",
                    }
                )
        for rule in result.get("business_rule", []) or []:
            rule_name = str(rule.get("name") or rule.get("rule_id") or "")
            rule_asset_id = f"business_rule.{self._slug(rule_name)}"
            for target in rule.get("applies_to") or []:
                target_text = str(target)
                target_type = target_text.split(".", 1)[0] if "." in target_text else "flow"
                relation_type = {
                    "flow": "applies_to_flow",
                    "process": "applies_to_process",
                    "plan": "applies_to_plan",
                }.get(target_type)
                if relation_type:
                    relationships.append(
                        {
                            "source_asset_id": rule_asset_id,
                            "type": relation_type,
                            "target_asset_id": target_text if "." in target_text else f"{target_type}.{self._slug(target_text)}",
                        }
                    )
        for process in result.get("process", []) or []:
            process_name = str(process.get("process_id") or process.get("name") or "")
            process_asset_id = f"process.{self._slug(process_name)}"
            for flow_id in process.get("related_flow_ids") or process.get("implements_flows") or []:
                relationships.append(
                    {
                        "source_asset_id": process_asset_id,
                        "type": "implements_flow",
                        "target_asset_id": str(flow_id) if str(flow_id).startswith("flow.") else f"flow.{flow_id}",
                    }
                )
        return relationships

    def _human_review_actions(self, asset_analysis: dict[str, Any]) -> list[dict[str, Any]]:
        actions: list[dict[str, Any]] = []
        asset_types = asset_analysis.get("asset_types") or {}
        for asset_type, summary in asset_types.items():
            if summary.get("candidate_count"):
                actions.append(
                    {
                        "action_type": "approve_asset_candidates",
                        "asset_type": asset_type,
                        "label": f"Review {asset_type} candidates",
                        "candidate_count": summary["candidate_count"],
                    }
                )
        for asset_type, payload in (asset_analysis.get("payloads") or {}).items():
            if payload.get("status") == "schema_defined_no_candidate":
                actions.append(
                    {
                        "action_type": "confirm_missing_asset_type",
                        "asset_type": asset_type,
                        "label": f"Confirm no {asset_type} assets were found",
                    }
                )
        if asset_analysis.get("aliases"):
            actions.append(
                {
                    "action_type": "approve_aliases",
                    "asset_type": "all",
                    "label": "Review alias and similarity candidates",
                    "candidate_count": len(asset_analysis["aliases"]),
                }
            )
        if asset_analysis.get("relationships"):
            actions.append(
                {
                    "action_type": "approve_relationships",
                    "asset_type": "all",
                    "label": "Review cross-asset relationships",
                    "candidate_count": len(asset_analysis["relationships"]),
                }
            )
        if asset_analysis.get("staged_asset_sets"):
            actions.append(
                {
                    "action_type": "approve_staged_asset_sets",
                    "asset_type": "all",
                    "label": "Review generated AssetSet YAML versions",
                    "candidate_count": len(asset_analysis["staged_asset_sets"]),
                }
            )
        return actions

    def _human_review_instructions(self) -> list[str]:
        return [
            "Review semantic classifications and extracted artifacts before graph loading.",
            "Review every discovered asset type, not only flows.",
            "Approve, reject, or correct actions, tools, entities, services, aliases, payloads, and relationships.",
            "Confirm whether asset types with schema_defined_no_candidate are truly absent from the corpus.",
            "Review generated AssetSet YAML manifests before promoting or deploying any version.",
            "Change status to approved when the artifacts can be loaded.",
            "Use reviewer_notes to document corrections, rejected assets, missing process definitions, or entity model gaps.",
        ]

    def _concept_names(self, result: dict[str, Any]) -> list[str]:
        values: list[str] = []
        for flow in result.get("flows", []):
            values.extend(str(value) for value in flow.get("concepts") or [])
            values.extend(str(value) for value in (flow.get("concept_aliases") or {}).keys())
        return self._dedupe_texts(values)

    @staticmethod
    def _dedupe_texts(values: list[Any]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            text = str(value or "").strip()
            key = text.casefold()
            if not text or key in seen:
                continue
            seen.add(key)
            result.append(text)
        return result

    @staticmethod
    def _slug(value: Any) -> str:
        return "_".join(str(value or "").casefold().replace(".", " ").replace("-", " ").split())

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

    @staticmethod
    def _run_id(started_at: str) -> str:
        return "".join(char if char.isalnum() else "-" for char in started_at).strip("-").lower()
