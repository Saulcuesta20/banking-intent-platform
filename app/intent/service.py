from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from app.approval.service import ApprovalService
from app.audit.service import AuditService
from app.capability.service import CapabilityService
from app.flow_context.service import FlowAnswerContextService
from app.intent.providers import SemanticReasoningProvider
from app.models import IntentResult
from app.retrieval.service import KnowledgeRetrievalService


class IntentClassificationService:
    def __init__(self, provider: SemanticReasoningProvider):
        self.provider = provider

    def classify(self, question: str, records):
        return self.provider.classify_intent(question, records)


class IntentResolutionService:
    def __init__(
        self,
        retrieval_service: KnowledgeRetrievalService,
        classification_service: IntentClassificationService,
        capability_service: CapabilityService,
        flow_context_service: FlowAnswerContextService,
        approval_service: ApprovalService,
        audit_service: AuditService,
        trace_directory: Path | None = None,
    ):
        self.retrieval_service = retrieval_service
        self.classification_service = classification_service
        self.capability_service = capability_service
        self.flow_context_service = flow_context_service
        self.approval_service = approval_service
        self.audit_service = audit_service
        self.trace_directory = trace_directory

    def resolve(self, question: str, trace: Callable[[str, str], None] | None = None) -> IntentResult:
        self._trace(trace, "input", f"question={question}")
        self._trace(trace, "retrieval", "loading flow/user-task knowledge")
        records = self.retrieval_service.retrieve(question)
        self._trace(trace, "retrieval", f"matched_records={len(records)}")
        if records:
            provider_name = records[0].metadata.get("retrieval_provider")
            if provider_name:
                self._trace(trace, "retrieval", f"provider={provider_name}")
            query_understanding = records[0].metadata.get("query_understanding")
            if query_understanding:
                self._trace(
                    trace,
                    "query_understanding",
                    f"provider={query_understanding.get('provider')} terms={query_understanding.get('search_terms')} entities={query_understanding.get('entities')}",
                )
            graph_summary = records[0].metadata.get("graph_query_summary")
            if graph_summary:
                self._trace(
                    trace,
                    "graph",
                    f"cypher_rows={graph_summary.get('rows_returned')} tokens={graph_summary.get('tokens')} fallback={graph_summary.get('fallback')}",
                )
            flow_ids = ", ".join(record.flow_id for record in records[:10])
            if flow_ids:
                self._trace(trace, "retrieval", f"candidate_flows={flow_ids}")

        registered_actions = self.capability_service.list_registered_actions()
        self._trace(trace, "capability", f"registered_actions={len(registered_actions)}")

        self._trace(trace, "intent", "classifying intent from retrieved records")
        record = self.classification_service.classify(question, records)

        if record is None:
            self._trace(trace, "intent", "no matching flow found")
            self._trace(trace, "resolution", "cannot_resolve=true reason=no flow knowledge matched")
            plan, tasks = self.approval_service.enforce(["clarify_customer_request"], [])
            result = IntentResult(
                flow_id="unknown",
                flow_name="Unknown flow",
                intent="unknown",
                confidence=0.0,
                business_event="UnknownBusinessQuestionAsked",
                requires_human_approval=self.approval_service.requires_approval(),
                plan=plan,
                tasks=tasks,
                related_capabilities=[],
                related_ontology_nodes=[],
                explanation="No flow knowledge matched the question.",
            )
            self.audit_service.record_intent_result(question, result)
            trace_path = self._write_ask_trace(question, records, None, None, result)
            if trace_path:
                self._trace(trace, "debug_trace", f"file={trace_path}")
            self._trace(trace, "audit", "recorded unknown intent result")
            return result

        self._trace(trace, "intent", f"selected flow={record.flow_id} confidence={record.confidence}")
        reasoning_provider = record.metadata.get("reasoning_provider")
        if reasoning_provider:
            self._trace(trace, "intent", f"provider={reasoning_provider}")
        llm_prompt_summary = record.metadata.get("llm_prompt_summary")
        if llm_prompt_summary:
            self._trace(
                trace,
                "llm",
                f"prompt_chars={llm_prompt_summary.get('chars')}",
            )
        llm_answer = record.metadata.get("llm_answer")
        if llm_answer:
            self._trace(
                trace,
                "llm",
                f"answer can_resolve={llm_answer.get('can_resolve')} selected_flow_id={llm_answer.get('selected_flow_id')} confidence={llm_answer.get('confidence')}",
            )
        llm_reason = record.metadata.get("llm_reason")
        if llm_reason:
            self._trace(trace, "llm", f"reason={llm_reason}")

        self._trace(trace, "flow_context", "projecting ingested event/plan/tasks/actions/ontology")
        context = self.flow_context_service.build(question, record)
        self._trace(trace, "flow_context", f"business_event={context.business_event}")
        self._trace(trace, "flow_context", f"plan_steps={len(context.plan)}")
        self._trace(trace, "flow_context", f"user_tasks={len(context.tasks)}")
        self._trace(trace, "flow_context", f"related_actions={len(context.related_capabilities)}")
        self._trace(trace, "flow_context", f"related_nodes={len(context.related_ontology_nodes)}")

        plan, tasks = self.approval_service.enforce(context.plan, context.tasks)
        self._trace(trace, "approval", f"requires_human_approval={self.approval_service.requires_approval()}")

        result = IntentResult(
            flow_id=record.flow_id,
            flow_name=record.flow_name,
            intent=record.intent,
            confidence=record.confidence,
            business_event=context.business_event,
            requires_human_approval=self.approval_service.requires_approval(),
            plan=plan,
            tasks=tasks,
            related_capabilities=context.related_capabilities,
            related_ontology_nodes=context.related_ontology_nodes,
            explanation=record.explanation,
        )
        self.audit_service.record_intent_result(question, result)
        trace_path = self._write_ask_trace(question, records, record, context, result)
        if trace_path:
            self._trace(trace, "debug_trace", f"file={trace_path}")
        self._trace(trace, "resolution", "can_resolve=true")
        self._trace(trace, "audit", "recorded intent result")
        return result

    def _trace(self, trace: Callable[[str, str], None] | None, component: str, message: str) -> None:
        if trace is not None:
            trace(component, message)

    def _write_ask_trace(
        self,
        question: str,
        records,
        selected_record,
        context,
        result: IntentResult,
    ) -> Path | None:
        if self.trace_directory is None:
            return None
        self.trace_directory.mkdir(parents=True, exist_ok=True)
        path = self.trace_directory / f"ask_trace_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
        first_metadata = records[0].metadata if records else {}
        selected_metadata = selected_record.metadata if selected_record is not None else {}
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "question": question,
            "retrieval": {
                "matched_records": len(records),
                "candidate_flows": [record.flow_id for record in records],
                "provider": first_metadata.get("retrieval_provider"),
            },
            "query_understanding": first_metadata.get("query_understanding"),
            "graph": {
                "query_summary": first_metadata.get("graph_query_summary"),
                "rows_preview": first_metadata.get("graph_rows_preview"),
            },
            "langchain_llm": {
                "provider": selected_metadata.get("reasoning_provider"),
                "prompt": selected_metadata.get("llm_prompt"),
                "prompt_summary": selected_metadata.get("llm_prompt_summary"),
                "answer": selected_metadata.get("llm_answer"),
                "reason": selected_metadata.get("llm_reason"),
            },
            "selected_flow": None
            if selected_record is None
            else {
                "flow_id": selected_record.flow_id,
                "flow_name": selected_record.flow_name,
                "intent": selected_record.intent,
                "confidence": selected_record.confidence,
                "business_event": selected_record.business_event,
                "source": selected_record.source,
            },
            "flow_context": None
            if context is None
            else {
                "business_event": context.business_event,
                "plan": context.plan,
                "tasks": [task.to_dict() for task in context.tasks],
                "related_capabilities": context.related_capabilities,
                "related_ontology_nodes": context.related_ontology_nodes,
            },
            "result": result.to_dict(),
        }
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return path
