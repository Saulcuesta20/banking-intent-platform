from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timezone
from importlib import import_module
from pathlib import Path
from typing import Any, NotRequired, TypedDict

from app.approval.service import ApprovalService
from app.audit.service import AuditService
from app.capability.service import CapabilityService
from app.flow_context.service import FlowAnswerContext
from app.flow_context.service import FlowAnswerContextService
from app.intent.providers import SemanticReasoningProvider
from app.models import IntentResult, KnowledgeRecord
from app.retrieval.service import KnowledgeRetrievalService


class AskState(TypedDict, total=False):
    question: str
    entities: list[str]
    retrieved_context: list[KnowledgeRecord]
    selected_flow: dict[str, Any]
    result: dict[str, Any]
    trace: NotRequired[Callable[[str, str], None] | None]
    selected_record: NotRequired[KnowledgeRecord | None]
    flow_context: NotRequired[FlowAnswerContext | None]
    result_model: NotRequired[IntentResult]


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
        use_langgraph_orchestration: bool = True,
    ):
        self.retrieval_service = retrieval_service
        self.classification_service = classification_service
        self.capability_service = capability_service
        self.flow_context_service = flow_context_service
        self.approval_service = approval_service
        self.audit_service = audit_service
        self.trace_directory = trace_directory
        self.use_langgraph_orchestration = use_langgraph_orchestration

    def resolve(self, question: str, trace: Callable[[str, str], None] | None = None) -> IntentResult:
        self._trace(
            trace,
            "call",
            "class=IntentResolutionService method=resolve input="
            + self._json({"question": question, "use_langgraph_orchestration": self.use_langgraph_orchestration}),
        )
        if self.use_langgraph_orchestration:
            return self._resolve_with_langgraph(question, trace)
        return self._resolve_linear(question, trace)

    def _resolve_with_langgraph(self, question: str, trace: Callable[[str, str], None] | None) -> IntentResult:
        self._trace(
            trace,
            "call",
            "class=IntentResolutionService method=_resolve_with_langgraph input="
            + self._json({"question": question}),
        )
        graph_module = self._optional_import("langgraph.graph", "langgraph")
        StateGraph = graph_module.StateGraph
        START = graph_module.START
        END = graph_module.END

        workflow = StateGraph(AskState)
        workflow.add_node("retrieve_context", self._ask_node_retrieve_context)
        workflow.add_node("classify_intent", self._ask_node_classify_intent)
        workflow.add_node("project_flow_context", self._ask_node_project_flow_context)
        workflow.add_node("unknown_result", self._ask_node_unknown_result)
        workflow.add_edge(START, "retrieve_context")
        workflow.add_edge("retrieve_context", "classify_intent")
        workflow.add_conditional_edges(
            "classify_intent",
            self._ask_route_after_classification,
            {
                "project": "project_flow_context",
                "unknown": "unknown_result",
            },
        )
        workflow.add_edge("project_flow_context", END)
        workflow.add_edge("unknown_result", END)
        self._trace(trace, "orchestration", "workflow=langgraph_ask")
        self._trace(
            trace,
            "orchestration",
            "workflow=langgraph_ask nodes="
            + self._json(["retrieve_context", "classify_intent", "project_flow_context", "unknown_result"]),
        )

        app = workflow.compile()
        final_state = app.invoke({"question": question, "trace": trace})
        result = final_state.get("result_model")
        if result is None:
            raise RuntimeError("LangGraph ask workflow finished without an IntentResult.")
        self._trace(
            trace,
            "call",
            "class=IntentResolutionService method=_resolve_with_langgraph output="
            + self._json({"flow_id": result.flow_id, "intent": result.intent, "confidence": result.confidence}),
        )
        return result

    def _resolve_linear(self, question: str, trace: Callable[[str, str], None] | None = None) -> IntentResult:
        self._trace(
            trace,
            "call",
            "class=IntentResolutionService method=_resolve_linear input=" + self._json({"question": question}),
        )
        self._trace(trace, "input", f"question={question}")
        self._trace(trace, "retrieval", "loading flow/user-task knowledge")
        records = self.retrieval_service.retrieve(question)
        self._trace(trace, "retrieval", f"matched_records={len(records)}")
        self._trace_retrieval_metadata(trace, records)

        registered_actions = self.capability_service.list_registered_actions()
        self._trace(trace, "capability", f"registered_actions={len(registered_actions)}")

        self._trace(trace, "intent", "classifying intent from retrieved records")
        record = self.classification_service.classify(question, records)
        if record is None:
            self._trace_llm_classifier_decision(trace)

        if record is None:
            return self._build_unknown_result(question, records, trace)

        return self._build_projected_result(question, records, record, trace)

    def _ask_node_retrieve_context(self, state: AskState) -> AskState:
        question = state["question"]
        trace = state.get("trace")
        self._trace(
            trace,
            "call",
            "class=IntentResolutionService method=_ask_node_retrieve_context input="
            + self._json({"question": question}),
        )
        self._trace(trace, "input", f"question={question}")
        self._trace(trace, "retrieval", "loading flow/user-task knowledge")
        records = self.retrieval_service.retrieve(question)
        self._trace(trace, "retrieval", f"matched_records={len(records)}")
        self._trace_retrieval_metadata(trace, records)
        registered_actions = self.capability_service.list_registered_actions()
        self._trace(trace, "capability", f"registered_actions={len(registered_actions)}")
        entities = []
        if records:
            query_understanding = records[0].metadata.get("query_understanding") or {}
            entities = list(query_understanding.get("entities") or [])
        self._trace(
            trace,
            "call",
            "class=IntentResolutionService method=_ask_node_retrieve_context output="
            + self._json({"records": len(records), "entities": entities}),
        )
        return {
            "retrieved_context": records,
            "entities": entities,
        }

    def _ask_node_classify_intent(self, state: AskState) -> AskState:
        question = state["question"]
        trace = state.get("trace")
        records = state.get("retrieved_context", [])
        self._trace(
            trace,
            "call",
            "class=IntentResolutionService method=_ask_node_classify_intent input="
            + self._json({"question": question, "candidate_flows": [record.flow_id for record in records]}),
        )
        self._trace(trace, "intent", "classifying intent from retrieved records")
        record = self.classification_service.classify(question, records)
        if record is None:
            self._trace_llm_classifier_decision(trace)
            self._trace(trace, "intent", "no matching flow found")
            self._trace(
                trace,
                "call",
                "class=IntentResolutionService method=_ask_node_classify_intent output="
                + self._json({"selected_record": None}),
            )
            return {
                "selected_record": None,
                "selected_flow": {},
            }
        self._trace(
            trace,
            "call",
            "class=IntentResolutionService method=_ask_node_classify_intent output="
            + self._json({"flow_id": record.flow_id, "intent": record.intent, "confidence": record.confidence}),
        )
        return {
            "selected_record": record,
            "selected_flow": {
                "flow_id": record.flow_id,
                "flow_name": record.flow_name,
                "intent": record.intent,
                "confidence": record.confidence,
            },
        }

    def _ask_route_after_classification(self, state: AskState) -> str:
        route = "project" if state.get("selected_record") is not None else "unknown"
        trace = state.get("trace")
        self._trace(
            trace,
            "orchestration",
            "class=IntentResolutionService method=_ask_route_after_classification output="
            + self._json({"route": route}),
        )
        return route

    def _ask_node_project_flow_context(self, state: AskState) -> AskState:
        self._trace(
            state.get("trace"),
            "call",
            "class=IntentResolutionService method=_ask_node_project_flow_context input="
            + self._json({"selected_flow": state.get("selected_flow")}),
        )
        result = self._build_projected_result(
            state["question"],
            state.get("retrieved_context", []),
            state["selected_record"],
            state.get("trace"),
        )
        return {
            "result": result.to_dict(),
            "result_model": result,
        }

    def _ask_node_unknown_result(self, state: AskState) -> AskState:
        result = self._build_unknown_result(
            state["question"],
            state.get("retrieved_context", []),
            state.get("trace"),
        )
        return {
            "result": result.to_dict(),
            "result_model": result,
        }

    def _build_unknown_result(
        self,
        question: str,
        records: list[KnowledgeRecord],
        trace: Callable[[str, str], None] | None,
    ) -> IntentResult:
        self._trace(trace, "resolution", "cannot_resolve=true reason=no flow knowledge matched")
        explanation = "No flow knowledge matched the question."
        query_understanding = records[0].metadata.get("query_understanding") if records else None
        ambiguity = query_understanding.get("ambiguity") if isinstance(query_understanding, dict) else None
        if ambiguity:
            option_text = ", ".join(self._format_ambiguity_option(option) for option in ambiguity.get("options", []))
            explanation = (
                "The request is ambiguous. The customer may need one of these flows: "
                f"{option_text}. Ask a clarification question before selecting an intent."
            )
            self._trace(trace, "intent", f"reason={ambiguity.get('reason')}")
        clarification_options = self._build_clarification_options(records)
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
            explanation=explanation,
            clarification_options=clarification_options,
        )
        self.audit_service.record_intent_result(question, result)
        trace_path = self._write_ask_trace(question, records, None, None, result)
        if trace_path:
            self._trace(trace, "debug_trace", f"file={trace_path}")
        self._trace(trace, "audit", "recorded unknown intent result")
        self._trace(
            trace,
            "call",
            "class=IntentResolutionService method=_build_unknown_result output="
            + self._json(result.to_dict()),
        )
        return result

    def _build_projected_result(
        self,
        question: str,
        records: list[KnowledgeRecord],
        record: KnowledgeRecord,
        trace: Callable[[str, str], None] | None,
    ) -> IntentResult:
        self._trace(
            trace,
            "call",
            "class=IntentResolutionService method=_build_projected_result input="
            + self._json({"question": question, "selected_flow": record.flow_id, "candidate_count": len(records)}),
        )
        self._trace_selected_record(trace, record)
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
        self._trace(
            trace,
            "call",
            "class=IntentResolutionService method=_build_projected_result output="
            + self._json(result.to_dict()),
        )
        return result

    def _trace_retrieval_metadata(
        self,
        trace: Callable[[str, str], None] | None,
        records: list[KnowledgeRecord],
    ) -> None:
        if not records:
            return
        provider_name = records[0].metadata.get("retrieval_provider")
        if provider_name:
            self._trace(trace, "retrieval", f"provider={provider_name}")
        retrieval_input = records[0].metadata.get("retrieval_input")
        if retrieval_input:
            self._trace(trace, "retrieval", "input=" + self._json(retrieval_input))
        retrieval_filter = records[0].metadata.get("retrieval_filter")
        if retrieval_filter:
            self._trace(trace, "retrieval", "filters=" + self._json(retrieval_filter))
        query_understanding = records[0].metadata.get("query_understanding")
        if query_understanding:
            self._trace(
                trace,
                "query_understanding",
                f"provider={query_understanding.get('provider')} terms={query_understanding.get('search_terms')} entities={query_understanding.get('entities')}",
            )
            self._trace(
                trace,
                "query_understanding",
                "output="
                + self._json(
                    {
                        "search_terms": query_understanding.get("search_terms"),
                        "corrected_question": query_understanding.get("corrected_question"),
                        "corrections": query_understanding.get("corrections"),
                        "entities": query_understanding.get("entities"),
                        "possible_intents": query_understanding.get("possible_intents"),
                        "ambiguity": query_understanding.get("ambiguity"),
                        "explanation": query_understanding.get("explanation"),
                    }
                ),
            )
        graph_summary = records[0].metadata.get("graph_query_summary")
        if graph_summary:
            self._trace(
                trace,
                "graph",
                f"cypher_rows={graph_summary.get('rows_returned')} tokens={graph_summary.get('tokens')} search_mode={graph_summary.get('search_mode')}",
            )
            self._trace(trace, "graph", "query=" + str(graph_summary.get("query")))
            self._trace(
                trace,
                "graph",
                "params=" + self._json({"tokens": graph_summary.get("tokens"), "limit": graph_summary.get("limit")}),
            )
        graph_rows_preview = records[0].metadata.get("graph_rows_preview")
        if graph_rows_preview:
            self._trace(trace, "graph", "rows_preview=" + self._json(graph_rows_preview))
        flow_ids = ", ".join(record.flow_id for record in records[:10])
        if flow_ids:
            self._trace(trace, "retrieval", f"candidate_flows={flow_ids}")

    def _trace_selected_record(
        self,
        trace: Callable[[str, str], None] | None,
        record: KnowledgeRecord,
    ) -> None:
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
            if llm_prompt_summary.get("preview"):
                self._trace(trace, "llm", f"prompt_preview={llm_prompt_summary.get('preview')}")
        llm_answer = record.metadata.get("llm_answer")
        if llm_answer:
            self._trace(
                trace,
                "llm",
                f"answer can_resolve={llm_answer.get('can_resolve')} selected_flow_id={llm_answer.get('selected_flow_id')} confidence={llm_answer.get('confidence')}",
            )
            self._trace(trace, "llm", "answer_json=" + self._json(llm_answer))
        llm_reason = record.metadata.get("llm_reason")
        if llm_reason:
            self._trace(trace, "llm", f"reason={llm_reason}")

    def _trace_llm_classifier_decision(self, trace: Callable[[str, str], None] | None) -> None:
        recorder = getattr(self.classification_service.provider, "decision_recorder", None)
        if recorder is None:
            return
        prompt = getattr(recorder, "prompt", "")
        answer = getattr(recorder, "answer", {})
        if prompt:
            summary = {"chars": len(prompt), "preview": prompt[:1200]}
            self._trace(trace, "llm", f"prompt_chars={summary['chars']}")
            self._trace(trace, "llm", f"prompt_preview={summary['preview']}")
        if answer:
            self._trace(
                trace,
                "llm",
                f"answer can_resolve={answer.get('can_resolve')} selected_flow_id={answer.get('selected_flow_id')} confidence={answer.get('confidence')}",
            )
            self._trace(trace, "llm", "answer_json=" + self._json(answer))
            if answer.get("reason"):
                self._trace(trace, "llm", f"reason={answer.get('reason')}")

    def _llm_classifier_trace_payload(self) -> dict[str, Any]:
        recorder = getattr(self.classification_service.provider, "decision_recorder", None)
        if recorder is None:
            return {
                "provider": None,
                "prompt": None,
                "prompt_summary": None,
                "answer": None,
                "reason": None,
            }
        prompt = getattr(recorder, "prompt", "")
        answer = getattr(recorder, "answer", {})
        return {
            "provider": "langchain_graph_rag_llm" if prompt or answer else None,
            "prompt": prompt or None,
            "prompt_summary": {"chars": len(prompt), "preview": prompt[:1200]} if prompt else None,
            "answer": answer or None,
            "reason": answer.get("reason") if isinstance(answer, dict) else None,
        }

    def _trace(self, trace: Callable[[str, str], None] | None, component: str, message: str) -> None:
        if trace is not None:
            trace(component, message)

    def _json(self, value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)

    def _format_ambiguity_option(self, option: Any) -> str:
        if isinstance(option, dict):
            flow_id = option.get("flow_id") or option.get("intent") or option.get("name") or "unknown"
            flow_name = option.get("flow_name")
            return f"{flow_id} ({flow_name})" if flow_name else str(flow_id)
        return str(option)

    def _build_clarification_options(self, records: list[KnowledgeRecord]) -> list[dict[str, Any]]:
        options: list[dict[str, Any]] = []
        seen: set[str] = set()
        first_metadata = records[0].metadata if records else {}
        query_understanding = first_metadata.get("query_understanding") or {}
        if isinstance(query_understanding, dict):
            ambiguity = query_understanding.get("ambiguity")
            if isinstance(ambiguity, dict):
                for option in ambiguity.get("options", []):
                    self._append_clarification_option(options, seen, option, "llm_ambiguity")
            for option in query_understanding.get("possible_intents", []):
                self._append_clarification_option(options, seen, option, "llm_possible_intent")
        for record in records[:6]:
            self._append_clarification_option(
                options,
                seen,
                {
                    "label": record.flow_name,
                    "flow_id": record.flow_id,
                    "intent": record.intent,
                    "reason": record.explanation,
                },
                "graph_candidate",
            )
        return options[:8]

    def _append_clarification_option(
        self,
        options: list[dict[str, Any]],
        seen: set[str],
        option: Any,
        source: str,
    ) -> None:
        if isinstance(option, dict):
            value = str(option.get("flow_id") or option.get("intent") or option.get("label") or option.get("name") or "")
            label = str(option.get("label") or option.get("name") or option.get("intent") or option.get("flow_id") or value)
            reason = option.get("reason")
            flow_id = option.get("flow_id")
            intent = option.get("intent")
        else:
            value = str(option)
            label = value.replace("_", " ").replace(".", " ").strip().title() or value
            reason = None
            flow_id = None
            intent = value
        key = value.strip().lower()
        if not key or key in seen:
            return
        seen.add(key)
        payload = {
            "label": label,
            "value": value,
            "source": source,
        }
        if flow_id:
            payload["flow_id"] = flow_id
        if intent:
            payload["intent"] = intent
        if reason:
            payload["reason"] = reason
        options.append(payload)

    def _optional_import(self, module_name: str, friendly_name: str | None = None):
        try:
            return import_module(module_name)
        except ImportError as exc:
            raise RuntimeError(
                f"Optional dependency '{friendly_name or module_name}' is required for ask orchestration."
            ) from exc

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
        timestamp = datetime.now(timezone.utc)
        path = self.trace_directory / f"ask_trace_{timestamp.strftime('%Y%m%dT%H%M%S%fZ')}.json"
        first_metadata = records[0].metadata if records else {}
        selected_metadata = selected_record.metadata if selected_record is not None else {}
        llm_trace = self._llm_classifier_trace_payload()
        payload = {
            "timestamp": timestamp.isoformat(),
            "question": question,
            "retrieval": {
                "matched_records": len(records),
                "candidate_flows": [record.flow_id for record in records],
                "provider": first_metadata.get("retrieval_provider"),
                "input": first_metadata.get("retrieval_input"),
                "filters": first_metadata.get("retrieval_filter"),
            },
            "query_understanding": first_metadata.get("query_understanding"),
            "graph": {
                "query_summary": first_metadata.get("graph_query_summary"),
                "rows_preview": first_metadata.get("graph_rows_preview"),
            },
            "langchain_llm": {
                "provider": selected_metadata.get("reasoning_provider") or llm_trace["provider"],
                "prompt": selected_metadata.get("llm_prompt") or llm_trace["prompt"],
                "prompt_summary": selected_metadata.get("llm_prompt_summary") or llm_trace["prompt_summary"],
                "answer": selected_metadata.get("llm_answer") or llm_trace["answer"],
                "reason": selected_metadata.get("llm_reason") or llm_trace["reason"],
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
