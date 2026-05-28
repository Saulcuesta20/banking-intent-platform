from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from app.ingestion.llm_flow_loader import CorpusDocument, LLMClient


IntentClass = Literal[
    "qa",
    "guided_use_case",
    "process_execution",
    "document_search",
    "approval",
    "human_escalation",
    "unknown",
]


@dataclass(frozen=True)
class SemanticChunkClassification:
    source: str
    intent_class: IntentClass
    knowledge_types: list[str] = field(default_factory=list)
    processes: list[str] = field(default_factory=list)
    systems: list[str] = field(default_factory=list)
    confidence: float = 0.0
    evidence: str = ""
    needs_human_review: bool = False
    review_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "intent_class": self.intent_class,
            "knowledge_types": self.knowledge_types,
            "processes": self.processes,
            "systems": self.systems,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "needs_human_review": self.needs_human_review,
            "review_reason": self.review_reason,
        }


@dataclass(frozen=True)
class SemanticAnalysisResult:
    classifications: list[SemanticChunkClassification] = field(default_factory=list)
    summary: str = ""
    review_required: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "review_required": self.review_required,
            "classifications": [item.to_dict() for item in self.classifications],
        }

    def to_prompt_context(self) -> str:
        if not self.classifications:
            return ""
        payload = self.to_dict()
        return (
            "Semantic analyzer candidate classifications. These are not final labels; "
            "use them as reviewable evidence during extraction:\n"
            f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
        )


class SemanticAnalyzerProvider(Protocol):
    def analyze(self, documents: list[CorpusDocument]) -> SemanticAnalysisResult:
        """Classify mixed enterprise corpus into reviewable intent/process evidence."""


class SemanticAnalyzerService:
    def __init__(self, provider: SemanticAnalyzerProvider):
        self.provider = provider

    def analyze(self, documents: list[CorpusDocument]) -> SemanticAnalysisResult:
        return self.provider.analyze(documents)


class HeuristicSemanticAnalyzerProvider:
    """Deterministic fallback for local ingestion and tests.

    This does not replace LLM classification. It creates conservative candidate
    labels and flags ambiguous fragments for human review.
    """

    QA_MARKERS = ("que ", "cual ", "por que", "como funciona", "que significa", "pregunta")
    GUIDED_MARKERS = ("ayudame", "guiame", "paso a paso", "iniciar", "vamos a empezar")
    EXECUTION_MARKERS = ("ejecuta", "crear ahora", "procesa", "confirma", "envia", "realiza", "registra")
    APPROVAL_MARKERS = ("aprobacion", "revision humana", "approval")
    ESCALATION_MARKERS = ("escala", "escalar", "riesgo legal", "fraude")

    def analyze(self, documents: list[CorpusDocument]) -> SemanticAnalysisResult:
        classifications = [self._classify_document(document) for document in documents if document.text]
        review_required = any(item.needs_human_review for item in classifications)
        return SemanticAnalysisResult(
            classifications=classifications,
            summary=(
                "Mixed enterprise corpus classified with deterministic heuristics. "
                "Use LLM semantic analysis or human review before applying artifacts."
            ),
            review_required=review_required,
        )

    def _classify_document(self, document: CorpusDocument) -> SemanticChunkClassification:
        text = document.text.lower()
        scores = {
            "qa": self._count(text, self.QA_MARKERS),
            "guided_use_case": self._count(text, self.GUIDED_MARKERS),
            "process_execution": self._count(text, self.EXECUTION_MARKERS),
            "approval": self._count(text, self.APPROVAL_MARKERS),
            "human_escalation": self._count(text, self.ESCALATION_MARKERS),
        }
        best = max(scores, key=scores.get)
        if scores[best] == 0:
            best = "unknown"
        strong_classes = [name for name, score in scores.items() if score > 0]
        needs_review = len(strong_classes) > 1 or best == "unknown"
        return SemanticChunkClassification(
            source=str(document.path),
            intent_class=best,  # type: ignore[arg-type]
            knowledge_types=self._knowledge_types(text),
            processes=self._processes(text),
            systems=self._systems(text),
            confidence=0.45 if needs_review else 0.65,
            evidence=document.text[:500],
            needs_human_review=needs_review,
            review_reason="mixed or ambiguous intent signals" if needs_review else "",
        )

    def _count(self, text: str, markers: tuple[str, ...]) -> int:
        return sum(text.count(marker) for marker in markers)

    def _knowledge_types(self, text: str) -> list[str]:
        candidates = []
        for marker, label in [
            ("regla", "rule"),
            ("excepcion", "exception"),
            ("document", "document"),
            ("sistema", "system"),
            ("protocolo", "integration"),
            ("aprobacion", "approval"),
        ]:
            if marker in text:
                candidates.append(label)
        return candidates

    def _processes(self, text: str) -> list[str]:
        processes = []
        for marker, process in [
            ("cuenta", "savings.account.opening"),
            ("prestamo", "loan.application"),
            ("credito", "loan.application"),
            ("transferencia", "money.transfer"),
            ("reclamo", "claim.filing"),
            ("onboarding", "customer.onboarding"),
        ]:
            if marker in text and process not in processes:
                processes.append(process)
        return processes

    def _systems(self, text: str) -> list[str]:
        systems = []
        for marker, system in [
            ("core banking", "core_banking"),
            ("loan origination", "loan_origination"),
            ("credit bureau", "credit_bureau"),
            ("mcp", "banking_policy_context"),
            ("grpc", "loan_scoring_service"),
            ("payments", "payments"),
            ("claims", "claims"),
        ]:
            if marker in text:
                systems.append(system)
        return systems


class LLMSemanticAnalyzerProvider:
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    def analyze(self, documents: list[CorpusDocument]) -> SemanticAnalysisResult:
        result = self.llm_client.complete_json(
            self._system_prompt(),
            self._user_content(documents),
        )
        classifications = [
            SemanticChunkClassification(
                source=str(item.get("source", "")),
                intent_class=self._intent_class(item.get("intent_class")),
                knowledge_types=[str(value) for value in item.get("knowledge_types", [])],
                processes=[str(value) for value in item.get("processes", [])],
                systems=[str(value) for value in item.get("systems", [])],
                confidence=float(item.get("confidence", 0.0) or 0.0),
                evidence=str(item.get("evidence", "")),
                needs_human_review=bool(item.get("needs_human_review", False)),
                review_reason=str(item.get("review_reason", "")),
            )
            for item in result.get("classifications", [])
            if isinstance(item, dict)
        ]
        return SemanticAnalysisResult(
            classifications=classifications,
            summary=str(result.get("summary", "")),
            review_required=bool(result.get("review_required", False)),
        )

    def _system_prompt(self) -> str:
        return (
            "You classify mixed enterprise banking corpus. The corpus is not pre-labeled. "
            "Detect hidden patterns for runtime intent routing: qa, guided_use_case, "
            "process_execution, document_search, approval, human_escalation, or unknown. "
            "Also identify knowledge types, related processes, systems, confidence, evidence, "
            "and whether a human reviewer must approve the extraction. Return only JSON."
        )

    def _user_content(self, documents: list[CorpusDocument]) -> str:
        blocks = [
            "Return this JSON shape:",
            "{",
            '  "summary": "short corpus analysis summary",',
            '  "review_required": true,',
            '  "classifications": [',
            "    {",
            '      "source": "file path",',
            '      "intent_class": "qa|guided_use_case|process_execution|document_search|approval|human_escalation|unknown",',
            '      "knowledge_types": ["policy|process|rule|exception|system|integration|faq|requirement"],',
            '      "processes": ["loan.application"],',
            '      "systems": ["loan_origination"],',
            '      "confidence": 0.0,',
            '      "evidence": "short grounded evidence",',
            '      "needs_human_review": true,',
            '      "review_reason": "why"',
            "    }",
            "  ]",
            "}",
        ]
        for doc in documents:
            if doc.text:
                blocks.append(f"\n--- SOURCE: {doc.path} ---\n{doc.text[:6000]}")
        return "\n".join(blocks)

    def _intent_class(self, value: Any) -> IntentClass:
        text = str(value or "unknown")
        allowed = {
            "qa",
            "guided_use_case",
            "process_execution",
            "document_search",
            "approval",
            "human_escalation",
            "unknown",
        }
        return text if text in allowed else "unknown"  # type: ignore[return-value]
