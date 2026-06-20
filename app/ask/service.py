from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timezone
from importlib import import_module
from pathlib import Path
from typing import Any, NotRequired, TypedDict

from app.approval.service import ApprovalService
from app.knowledge_base.models import EvidenceBundle
from app.knowledge_base.search import AssetSearchService
from app.audit.service import AuditService
from app.capability.service import CapabilityService
from app.ask.answer import AnswerBuilder
from app.ask.answer import AnswerContext
from app.ask.intent import FlowSelectionService
from app.ask.understanding import QuestionUnderstanding, QuestionUnderstandingService
from app.models import AnswerResult, KnowledgeRecord
from app.knowledge_base.service import KnowledgeBaseService
from app.planning.models import PlanningTrace
from app.planning.service import PlanningService


class AskState(TypedDict, total=False):
    question: str
    entities: list[str]
    knowledge_candidates: list[KnowledgeRecord]
    question_understanding: dict[str, Any]
    selected_flow: dict[str, Any]
    result: dict[str, Any]
    trace: NotRequired[Callable[[str, str], None] | None]
    selected_record: NotRequired[KnowledgeRecord | None]
    answer_context: NotRequired[AnswerContext | None]
    result_model: NotRequired[AnswerResult]
    planning_trace: NotRequired[dict[str, Any]]
    asset_search: NotRequired[dict[str, Any]]
    evidence_bundle: NotRequired[dict[str, Any]]


class AskService:
    def __init__(
        self,
        knowledge_base_service: KnowledgeBaseService,
        question_understanding_service: QuestionUnderstandingService,
        flow_selection_service: FlowSelectionService,
        capability_service: CapabilityService,
        answer_builder: AnswerBuilder,
        approval_service: ApprovalService,
        audit_service: AuditService,
        planning_service: PlanningService | None = None,
        asset_search_service: AssetSearchService | None = None,
        trace_directory: Path | None = None,
        use_langgraph_orchestration: bool = True,
    ):
        self.knowledge_base_service = knowledge_base_service
        self.question_understanding_service = question_understanding_service
        self.flow_selection_service = flow_selection_service
        self.capability_service = capability_service
        self.answer_builder = answer_builder
        self.approval_service = approval_service
        self.audit_service = audit_service
        self.planning_service = planning_service or PlanningService()
        self.asset_search_service = asset_search_service
        self.trace_directory = trace_directory
        self.use_langgraph_orchestration = use_langgraph_orchestration

    def resolve(self, question: str, trace: Callable[[str, str], None] | None = None) -> AnswerResult:
        self._trace(
            trace,
            "call",
            "class=AskService method=resolve input="
            + self._json({"question": question, "use_langgraph_orchestration": self.use_langgraph_orchestration}),
        )
        if self.use_langgraph_orchestration:
            return self._resolve_with_langgraph(question, trace)
        return self._resolve_linear(question, trace)

    def _resolve_with_langgraph(self, question: str, trace: Callable[[str, str], None] | None) -> AnswerResult:
        self._trace(
            trace,
            "call",
            "class=AskService method=_resolve_with_langgraph input="
            + self._json({"question": question}),
        )
        graph_module = self._optional_import("langgraph.graph", "langgraph")
        StateGraph = graph_module.StateGraph
        START = graph_module.START
        END = graph_module.END

        workflow = StateGraph(AskState)
        workflow.add_node("understand_question", self._ask_node_understand_question)
        workflow.add_node("search_knowledge", self._ask_node_search_knowledge)
        workflow.add_node("analyze_goal", self._ask_node_analyze_goal)
        workflow.add_node("answer_question", self._ask_node_answer_question)
        workflow.add_node("select_intent", self._ask_node_select_intent)
        workflow.add_node("build_answer", self._ask_node_build_answer)
        workflow.add_node("unknown_result", self._ask_node_unknown_result)
        workflow.add_edge(START, "understand_question")
        workflow.add_edge("understand_question", "search_knowledge")
        workflow.add_edge("search_knowledge", "analyze_goal")
        workflow.add_conditional_edges(
            "analyze_goal",
            self._ask_route_after_planning,
            {
                "qa": "answer_question",
                "select": "select_intent",
            },
        )
        workflow.add_conditional_edges(
            "select_intent",
            self._ask_route_after_selection,
            {
                "project": "build_answer",
                "unknown": "unknown_result",
            },
        )
        workflow.add_edge("answer_question", END)
        workflow.add_edge("build_answer", END)
        workflow.add_edge("unknown_result", END)
        self._trace(trace, "orchestration", "workflow=langgraph_ask")
        self._trace(
            trace,
            "orchestration",
            "workflow=langgraph_ask nodes="
            + self._json(
                [
                    "understand_question",
                    "search_knowledge",
                    "analyze_goal",
                    "answer_question",
                    "select_intent",
                    "build_answer",
                    "unknown_result",
                ]
            ),
        )

        app = workflow.compile()
        final_state = app.invoke({"question": question, "trace": trace})
        result = final_state.get("result_model")
        if result is None:
            raise RuntimeError("LangGraph ask workflow finished without an AnswerResult.")
        self._trace(
            trace,
            "call",
            "class=AskService method=_resolve_with_langgraph output="
            + self._json({"flow_id": result.flow_id, "intent": result.intent, "confidence": result.confidence}),
        )
        return result

    def _resolve_linear(self, question: str, trace: Callable[[str, str], None] | None = None) -> AnswerResult:
        self._trace(
            trace,
            "call",
            "class=AskService method=_resolve_linear input=" + self._json({"question": question}),
        )
        self._trace(trace, "input", f"question={question}")
        understanding = self.question_understanding_service.understand(question)
        self._trace_question_understanding(trace, understanding)
        self._trace(trace, "knowledge_base", "searching approved knowledge")
        records = self._attach_understanding(
            self.knowledge_base_service.search(understanding.search_terms),
            understanding,
        )
        self._trace(trace, "knowledge_base", f"matched_records={len(records)}")
        self._trace_knowledge_metadata(trace, records)
        asset_search = self._search_assets(question, trace)
        evidence_bundle = self._build_evidence_bundle(question, understanding, records, asset_search, trace)

        registered_tools = self.capability_service.list_registered_tools()
        self._trace(trace, "tools", f"registered_tools={len(registered_tools)}")
        planning_trace = self.planning_service.analyze(question, records, registered_tools, understanding, asset_search)
        self._trace_planning(trace, planning_trace)
        if self._is_direct_question_route(planning_trace):
            return self._build_question_answer_result(question, records, trace, planning_trace, asset_search, evidence_bundle)

        self._trace(trace, "intent", "classifying intent from retrieved records")
        record = self.flow_selection_service.select(question, records)
        if record is None:
            self._trace_llm_classifier_decision(trace)

        if record is None:
            return self._build_unknown_result(question, records, trace, planning_trace, asset_search, evidence_bundle)

        return self._build_projected_result(question, records, record, trace, planning_trace, asset_search, evidence_bundle)

    def _ask_node_understand_question(self, state: AskState) -> AskState:
        understanding = self.question_understanding_service.understand(state["question"])
        self._trace_question_understanding(state.get("trace"), understanding)
        return {
            "question_understanding": understanding.__dict__,
            "entities": list(understanding.entities),
        }

    def _ask_node_search_knowledge(self, state: AskState) -> AskState:
        question = state["question"]
        trace = state.get("trace")
        self._trace(
            trace,
            "call",
            "class=AskService method=_ask_node_search_knowledge input="
            + self._json({"question": question}),
        )
        self._trace(trace, "input", f"question={question}")
        self._trace(trace, "knowledge_base", "searching approved knowledge")
        understanding = QuestionUnderstanding(**state["question_understanding"])
        records = self.knowledge_base_service.search(understanding.search_terms)
        understanding = self._reconcile_exact_graph_match(question, understanding, records, trace)
        records = self._attach_understanding(records, understanding)
        self._trace(trace, "knowledge_base", f"matched_records={len(records)}")
        self._trace_knowledge_metadata(trace, records)
        asset_search = self._search_assets(question, trace)
        evidence_bundle = self._build_evidence_bundle(question, understanding, records, asset_search, trace)
        registered_tools = self.capability_service.list_registered_tools()
        self._trace(trace, "tools", f"registered_tools={len(registered_tools)}")
        self._trace(
            trace,
            "call",
            "class=AskService method=_ask_node_search_knowledge output="
            + self._json({"records": len(records), "entities": understanding.entities}),
        )
        return {
            "knowledge_candidates": records,
            "question_understanding": understanding.__dict__,
            "asset_search": asset_search,
            "evidence_bundle": evidence_bundle.to_trace_payload(),
        }

    def _ask_node_analyze_goal(self, state: AskState) -> AskState:
        question = state["question"]
        trace = state.get("trace")
        records = state.get("knowledge_candidates", [])
        registered_tools = self.capability_service.list_registered_tools()
        understanding = QuestionUnderstanding(**state["question_understanding"])
        planning_trace = self.planning_service.analyze(question, records, registered_tools, understanding, state.get("asset_search"))
        self._trace_planning(trace, planning_trace)
        return {
            "planning_trace": planning_trace.to_dict(),
        }

    def _ask_route_after_planning(self, state: AskState) -> str:
        planning_trace = self._planning_trace_from_state(state)
        route = "qa" if planning_trace is not None and self._is_direct_question_route(planning_trace) else "select"
        trace = state.get("trace")
        self._trace(
            trace,
            "orchestration",
            "class=AskService method=_ask_route_after_planning output="
            + self._json({"route": route}),
        )
        return route

    def _ask_node_answer_question(self, state: AskState) -> AskState:
        result = self._build_question_answer_result(
            state["question"],
            state.get("knowledge_candidates", []),
            state.get("trace"),
            self._planning_trace_from_state(state),
            state.get("asset_search"),
            self._evidence_bundle_from_state(state),
        )
        return {
            "result": result.to_dict(),
            "result_model": result,
        }

    def _ask_node_select_intent(self, state: AskState) -> AskState:
        question = state["question"]
        trace = state.get("trace")
        records = state.get("knowledge_candidates", [])
        self._trace(
            trace,
            "call",
            "class=AskService method=_ask_node_select_intent input="
            + self._json({"question": question, "candidate_flows": [record.flow_id for record in records]}),
        )
        self._trace(trace, "intent", "classifying intent from retrieved records")
        record = self.flow_selection_service.select(question, records)
        if record is None:
            self._trace_llm_classifier_decision(trace)
            self._trace(trace, "intent", "no matching flow found")
            self._trace(
                trace,
                "call",
                "class=AskService method=_ask_node_select_intent output="
                + self._json({"selected_record": None}),
            )
            return {
                "selected_record": None,
                "selected_flow": {},
            }
        self._trace(
            trace,
            "call",
            "class=AskService method=_ask_node_select_intent output="
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

    def _ask_route_after_selection(self, state: AskState) -> str:
        route = "project" if state.get("selected_record") is not None else "unknown"
        trace = state.get("trace")
        self._trace(
            trace,
            "orchestration",
            "class=AskService method=_ask_route_after_selection output="
            + self._json({"route": route}),
        )
        return route

    def _ask_node_build_answer(self, state: AskState) -> AskState:
        self._trace(
            state.get("trace"),
            "call",
            "class=AskService method=_ask_node_build_answer input="
            + self._json({"selected_flow": state.get("selected_flow")}),
        )
        result = self._build_projected_result(
            state["question"],
            state.get("knowledge_candidates", []),
            state["selected_record"],
            state.get("trace"),
            self._planning_trace_from_state(state),
            state.get("asset_search"),
            self._evidence_bundle_from_state(state),
        )
        return {
            "result": result.to_dict(),
            "result_model": result,
        }

    def _ask_node_unknown_result(self, state: AskState) -> AskState:
        result = self._build_unknown_result(
            state["question"],
            state.get("knowledge_candidates", []),
            state.get("trace"),
            self._planning_trace_from_state(state),
            state.get("asset_search"),
            self._evidence_bundle_from_state(state),
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
        planning_trace: PlanningTrace | None = None,
        asset_search: dict[str, Any] | None = None,
        evidence_bundle: EvidenceBundle | dict[str, Any] | None = None,
    ) -> AnswerResult:
        self._trace(trace, "resolution", "cannot_resolve=true reason=no flow knowledge matched")
        explanation = "No flow knowledge matched the question."
        question_understanding = records[0].metadata.get("question_understanding") if records else None
        ambiguity = question_understanding.get("ambiguity") if isinstance(question_understanding, dict) else None
        if ambiguity:
            option_text = ", ".join(self._format_ambiguity_option(option) for option in ambiguity.get("options", []))
            explanation = (
                "The request is ambiguous. The customer may need one of these flows: "
                f"{option_text}. Ask a clarification question before selecting an intent."
            )
            self._trace(trace, "intent", f"reason={ambiguity.get('reason')}")
        clarification_options = self._build_clarification_options(records)
        plan, tasks = self.approval_service.enforce(["clarify_customer_request"], [])
        result = AnswerResult(
            flow_id="unknown",
            flow_name="Unknown flow",
            intent="unknown",
            confidence=0.0,
            business_event="UnknownBusinessQuestionAsked",
            requires_human_approval=self.approval_service.requires_approval(),
            plan=plan,
            tasks=tasks,
            related_capabilities=[],
            related_concepts=[],
            explanation=explanation,
            clarification_options=clarification_options,
            **self._planning_result_fields(planning_trace),
        )
        self.audit_service.record_intent_result(question, result)
        trace_path = self._write_ask_trace(question, records, None, None, result, asset_search, evidence_bundle)
        if trace_path:
            self._trace(trace, "debug_trace", f"file={trace_path}")
        self._trace(trace, "audit", "recorded unknown intent result")
        self._trace(
            trace,
            "call",
            "class=AskService method=_build_unknown_result output="
            + self._json(result.to_dict()),
        )
        return result

    def _build_question_answer_result(
        self,
        question: str,
        records: list[KnowledgeRecord],
        trace: Callable[[str, str], None] | None,
        planning_trace: PlanningTrace | None = None,
        asset_search: dict[str, Any] | None = None,
        evidence_bundle: EvidenceBundle | dict[str, Any] | None = None,
    ) -> AnswerResult:
        self._trace(trace, "resolution", "can_resolve=true route=qa_answer")
        explanation = self._qa_explanation(planning_trace)
        result = AnswerResult(
            flow_id="qa.answer",
            flow_name="Question Answer",
            intent="qa.answer",
            confidence=0.8,
            business_event="QuestionAnswered",
            requires_human_approval=False,
            plan=[],
            tasks=[],
            related_capabilities=[],
            related_concepts=self._qa_related_concepts(records),
            explanation=explanation,
            **self._planning_result_fields(planning_trace),
        )
        self.audit_service.record_intent_result(question, result)
        trace_path = self._write_ask_trace(question, records, None, None, result, asset_search, evidence_bundle)
        if trace_path:
            self._trace(trace, "debug_trace", f"file={trace_path}")
        self._trace(trace, "audit", "recorded question answer result")
        self._trace(
            trace,
            "call",
            "class=AskService method=_build_question_answer_result output="
            + self._json(result.to_dict()),
        )
        return result

    def _build_projected_result(
        self,
        question: str,
        records: list[KnowledgeRecord],
        record: KnowledgeRecord,
        trace: Callable[[str, str], None] | None,
        planning_trace: PlanningTrace | None = None,
        asset_search: dict[str, Any] | None = None,
        evidence_bundle: EvidenceBundle | dict[str, Any] | None = None,
    ) -> AnswerResult:
        self._trace(
            trace,
            "call",
            "class=AskService method=_build_projected_result input="
            + self._json({"question": question, "selected_flow": record.flow_id, "candidate_count": len(records)}),
        )
        self._trace_selected_record(trace, record)
        self._trace(trace, "answer", "projecting ingested event/plan/tasks/tools/concepts")
        context = self.answer_builder.build(question, record)
        self._trace(trace, "answer", f"business_event={context.business_event}")
        self._trace(trace, "answer", f"plan_steps={len(context.plan)}")
        self._trace(trace, "answer", f"user_tasks={len(context.tasks)}")
        self._trace(trace, "answer", f"related_tools={len(context.related_capabilities)}")
        self._trace(trace, "answer", f"related_concepts={len(context.related_concepts)}")

        plan, tasks = self.approval_service.enforce(context.plan, context.tasks)
        self._trace(trace, "approval", f"requires_human_approval={self.approval_service.requires_approval()}")

        result = AnswerResult(
            flow_id=record.flow_id,
            flow_name=record.flow_name,
            intent=record.intent,
            confidence=record.confidence,
            business_event=context.business_event,
            requires_human_approval=self.approval_service.requires_approval(),
            plan=plan,
            tasks=tasks,
            related_capabilities=context.related_capabilities,
            related_concepts=context.related_concepts,
            explanation=record.explanation,
            **self._planning_result_fields(planning_trace),
        )
        self.audit_service.record_intent_result(question, result)
        trace_path = self._write_ask_trace(question, records, record, context, result, asset_search, evidence_bundle)
        if trace_path:
            self._trace(trace, "debug_trace", f"file={trace_path}")
        self._trace(trace, "resolution", "can_resolve=true")
        self._trace(trace, "audit", "recorded intent result")
        self._trace(
            trace,
            "call",
            "class=AskService method=_build_projected_result output="
            + self._json(result.to_dict()),
        )
        return result

    def _trace_planning(self, trace: Callable[[str, str], None] | None, planning_trace: PlanningTrace) -> None:
        route = planning_trace.route
        self._trace(trace, "planning", f"goal={planning_trace.goal.summary}")
        self._trace(trace, "planning", f"route_mode={route.mode}")
        self._trace(trace, "planning", f"needs={len(planning_trace.user_needs)}")
        self._trace(trace, "planning", "output=" + self._json(planning_trace.to_dict()))

    def _is_direct_question_route(self, planning_trace: PlanningTrace) -> bool:
        actions = {need.resolution_action for need in planning_trace.user_needs}
        qa_targets = [
            target
            for need in planning_trace.user_needs
            for target in need.known_targets
            if target.type in {"qa", "business_rule"}
        ]
        return actions == {"answer_question"} and bool(qa_targets)

    def _qa_explanation(self, planning_trace: PlanningTrace | None) -> str:
        if planning_trace is None:
            return "Direct answer based on known question context."
        target_ids = [
            target.id
            for need in planning_trace.user_needs
            for target in need.known_targets
        ]
        if "qa.automatic_payment_account_required" in target_ids:
            return (
                "Depende de si ya tienes una cuenta elegible para pago automatico. "
                "Si ya existe una cuenta compatible, no necesitas abrir otra; si no existe, "
                "puedes continuar con una opcion de apertura de cuenta antes de configurar el pago."
            )
        return "Direct answer based on the matched known question route."

    def _qa_related_concepts(self, records: list[KnowledgeRecord]) -> list[str]:
        values = []
        seen = set()
        for record in records[:3]:
            for concept in record.concepts:
                if concept not in seen:
                    values.append(concept)
                    seen.add(concept)
        return values[:8]

    def _planning_trace_from_state(self, state: AskState) -> PlanningTrace | None:
        raw = state.get("planning_trace")
        if not isinstance(raw, dict):
            return None
        return PlanningTrace(**raw)

    def _planning_result_fields(self, planning_trace: PlanningTrace | None) -> dict[str, Any]:
        if planning_trace is None:
            return {}
        payload = planning_trace.to_dict()
        return {
            "goal": payload["goal"],
            "user_needs": payload["user_needs"],
            "route": payload["route"],
            "multiple_intentions_plan": payload["multiple_intentions_plan"],
            "requires_execution_confirmation": self._requires_execution_confirmation(payload),
            "execution_selection_policy": self._execution_selection_policy(payload),
            "execution_options": self._execution_options(payload),
        }

    def _requires_execution_confirmation(self, planning_payload: dict[str, Any]) -> bool:
        actions = {
            need.get("resolution_action")
            for need in planning_payload.get("user_needs", [])
        }
        return actions != {"answer_question"}

    def _execution_selection_policy(self, planning_payload: dict[str, Any]) -> dict[str, Any]:
        route = planning_payload.get("route") or {}
        mode = route.get("mode") or "unknown"
        actions = [
            need.get("resolution_action")
            for need in planning_payload.get("user_needs", [])
            if need.get("resolution_action")
        ]
        if actions == ["answer_question"] or set(actions) == {"answer_question"}:
            return {
                "path": "qa_route",
                "selection_mode": "none",
                "requires_user_selection": False,
                "reason": "Direct answers do not execute tools or processes.",
            }
        if mode == "multiple_intentions":
            return {
                "path": "multiple_intentions_route",
                "selection_mode": "multiple",
                "requires_user_selection": True,
                "reason": "Multiple intentions route contains complementary options; the user may choose one or many.",
            }
        if mode == "clarification":
            return {
                "path": "clarification_route",
                "selection_mode": "single",
                "requires_user_selection": True,
                "reason": "Clarification route contains competing intentions; the user must choose one.",
            }
        if "invoke_known_process" in actions:
            return {
                "path": "process_route",
                "selection_mode": "single",
                "requires_user_selection": True,
                "reason": "A process route must be confirmed before execution.",
            }
        if "invoke_known_flow" in actions:
            return {
                "path": "flow_route",
                "selection_mode": "single",
                "requires_user_selection": True,
                "reason": "A flow route must be confirmed before execution.",
            }
        return {
            "path": "unknown_route",
            "selection_mode": "single",
            "requires_user_selection": True,
            "reason": "The route requires explicit validation before any execution.",
        }

    def _execution_options(self, planning_payload: dict[str, Any]) -> list[dict[str, Any]]:
        route = planning_payload.get("route") or {}
        user_needs = planning_payload.get("user_needs") or []
        multiple_intentions_plan = planning_payload.get("multiple_intentions_plan") or {}
        options: list[dict[str, Any]] = []
        if route.get("mode") == "multiple_intentions" and multiple_intentions_plan.get("steps"):
            options.append(
                {
                    "option_id": "continue_multiple_intentions_plan",
                    "label": "Continuar con el plan de multiples intenciones completo",
                    "resolution_action": "compose_multiple_intentions_plan",
                    "target_ids": [
                        target.get("id")
                        for target in multiple_intentions_plan.get("selected_targets", [])
                        if target.get("id")
                    ],
                    "plan_steps": [step.get("step") for step in multiple_intentions_plan.get("steps", []) if step.get("step")],
                    "executes_tools_now": False,
                    "requires_confirmation": True,
                    "selection_group": "complementary",
                }
            )
        for index, need in enumerate(user_needs, start=1):
            targets = need.get("known_targets") or []
            action = need.get("resolution_action") or "unknown"
            options.append(
                {
                    "option_id": f"need_{index}",
                    "label": self._execution_option_label(action, targets),
                    "resolution_action": action,
                    "target_ids": [target.get("id") for target in targets if target.get("id")],
                    "source_need_id": need.get("need_id"),
                    "source_text": need.get("text"),
                    "executes_tools_now": False,
                    "requires_confirmation": True,
                    "selection_group": "complementary" if route.get("mode") == "multiple_intentions" else "competing",
                }
            )
        options.append(
            {
                "option_id": "do_not_execute",
                "label": "No ejecutar nada todavia",
                "resolution_action": "reject_unsupported",
                "target_ids": [],
                "executes_tools_now": False,
                "requires_confirmation": False,
                "selection_group": "control",
            }
        )
        return options

    def _execution_option_label(self, action: str, targets: list[dict[str, Any]]) -> str:
        first_target = targets[0] if targets else {}
        target_id = first_target.get("id")
        if action == "invoke_known_flow":
            return f"Continuar con flujo {target_id}" if target_id else "Continuar con flujo conocido"
        if action == "invoke_known_process":
            return f"Continuar con proceso {target_id}" if target_id else "Continuar con proceso conocido"
        if action == "explain_tool":
            return f"Solo explicar herramienta {target_id}" if target_id else "Solo explicar herramienta"
        if action == "answer_question":
            return "Solo responder la pregunta"
        if action == "ask_clarification":
            return "Pedir aclaracion antes de continuar"
        return "Revisar esta opcion"

    def _trace_knowledge_metadata(
        self,
        trace: Callable[[str, str], None] | None,
        records: list[KnowledgeRecord],
    ) -> None:
        if not records:
            return
        provider_name = records[0].metadata.get("knowledge_provider")
        if provider_name:
            self._trace(trace, "knowledge_base", f"provider={provider_name}")
        knowledge_input = records[0].metadata.get("knowledge_input")
        if knowledge_input:
            self._trace(trace, "knowledge_base", "input=" + self._json(knowledge_input))
        knowledge_filter = records[0].metadata.get("knowledge_filter")
        if knowledge_filter:
            self._trace(trace, "knowledge_base", "filters=" + self._json(knowledge_filter))
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
            self._trace(trace, "knowledge_base", f"candidate_flows={flow_ids}")

    def _search_assets(self, question: str, trace: Callable[[str, str], None] | None) -> dict[str, Any]:
        if self.asset_search_service is None:
            return {"enabled": False}
        result = self.asset_search_service.search(question)
        payload = {
            "enabled": True,
            "query": result.query,
            "primary_assets": [asset.asset_id for asset in result.primary_assets],
            "supporting_assets": [asset.asset_id for asset in result.supporting_assets],
            "evidence_assets": [asset.asset_id for asset in result.evidence_assets],
            "structural_layers": sorted(
                {
                    layer
                    for asset in result.all_assets()
                    for layer in [
                        asset.structural_layer
                        or asset.payload.get("structural_layer")
                        or asset.business_layer
                        or asset.payload.get("business_layer")
                    ]
                    if layer
                }
            ),
            "semantic_spaces": sorted(
                {
                    str(space)
                    for asset in result.all_assets()
                    for space in [
                        asset.payload.get("semantic_space"),
                        *(asset.payload.get("semantic_spaces") or [] if isinstance(asset.payload.get("semantic_spaces"), list) else []),
                    ]
                    if space
                }
            ),
        }
        self._trace(
            trace,
            "asset_search",
            "output=" + self._json(payload),
        )
        return payload

    def _build_evidence_bundle(
        self,
        question: str,
        understanding: QuestionUnderstanding,
        records: list[KnowledgeRecord],
        asset_search: dict[str, Any],
        trace: Callable[[str, str], None] | None,
    ) -> EvidenceBundle:
        bundle = self.knowledge_base_service.build_evidence_bundle(
            question=question,
            search_terms=understanding.search_terms,
            records=records,
            question_understanding=understanding.__dict__,
            asset_search=asset_search,
        )
        payload = bundle.to_trace_payload()
        self._trace(trace, "knowledge_source_router", "routes=" + self._json(payload["routes"]))
        self._trace(trace, "evidence_bundle", "summary=" + self._json(payload))
        return bundle

    @staticmethod
    def _evidence_bundle_from_state(state: AskState) -> dict[str, Any] | None:
        evidence_bundle = state.get("evidence_bundle")
        return evidence_bundle if isinstance(evidence_bundle, dict) else None

    def _trace_question_understanding(
        self,
        trace: Callable[[str, str], None] | None,
        understanding: QuestionUnderstanding,
    ) -> None:
        self._trace(
            trace,
            "question_understanding",
            f"provider={understanding.provider} terms={understanding.search_terms} entities={understanding.entities}",
        )
        self._trace(trace, "question_understanding", "output=" + self._json(understanding.__dict__))

    def _attach_understanding(
        self,
        records: list[KnowledgeRecord],
        understanding: QuestionUnderstanding,
    ) -> list[KnowledgeRecord]:
        return [
            record.model_copy(
                update={"metadata": {**record.metadata, "question_understanding": understanding.__dict__}}
            )
            for record in records
        ]

    def _reconcile_exact_graph_match(
        self,
        question: str,
        understanding: QuestionUnderstanding,
        records: list[KnowledgeRecord],
        trace: Callable[[str, str], None] | None,
    ) -> QuestionUnderstanding:
        normalized_question = self._normalize_utterance(question)
        exact_records = [
            record
            for record in records
            if any(
                self._normalize_utterance(utterance) == normalized_question
                for utterance in record.utterances
            )
        ]
        if len(exact_records) != 1:
            return understanding
        record = exact_records[0]
        reconciled = replace(
            understanding,
            possible_intents=[record.intent],
            ask_posture="execution_request",
            routing_hints={
                **understanding.routing_hints,
                "needs_flow": True,
                "needs_process": True,
                "needs_clarification": False,
                "intention_relation": "single",
            },
            ambiguity={
                "is_ambiguous": False,
                "reason": "Unique exact utterance match in the approved graph.",
                "options": [],
            },
            explanation=(
                f"{understanding.explanation} Exact approved graph match: {record.flow_id}."
            ),
        )
        self._trace(
            trace,
            "question_understanding",
            f"exact_graph_match={record.flow_id} ambiguity=false",
        )
        return reconciled

    @staticmethod
    def _normalize_utterance(value: str) -> str:
        return " ".join(re.findall(r"[a-z0-9áéíóúñ]+", value.casefold()))

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
        recorder = getattr(self.flow_selection_service.provider, "decision_recorder", None)
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
        recorder = getattr(self.flow_selection_service.provider, "decision_recorder", None)
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
        question_understanding = first_metadata.get("question_understanding") or {}
        if isinstance(question_understanding, dict):
            ambiguity = question_understanding.get("ambiguity")
            if isinstance(ambiguity, dict):
                for option in ambiguity.get("options", []):
                    self._append_clarification_option(options, seen, option, "llm_ambiguity")
            for option in question_understanding.get("possible_intents", []):
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
        result: AnswerResult,
        asset_search: dict[str, Any] | None = None,
        evidence_bundle: EvidenceBundle | dict[str, Any] | None = None,
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
            "knowledge_search": {
                "matched_records": len(records),
                "candidate_flows": [record.flow_id for record in records],
                "provider": first_metadata.get("knowledge_provider"),
                "input": first_metadata.get("knowledge_input"),
                "filters": first_metadata.get("knowledge_filter"),
            },
            "asset_search": asset_search or {"enabled": False},
            "evidence_bundle": self._evidence_trace_payload(evidence_bundle),
            "question_understanding": first_metadata.get("question_understanding"),
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
            "answer": None
            if context is None
            else {
                "business_event": context.business_event,
                "plan": context.plan,
                "tasks": [task.to_dict() for task in context.tasks],
                "related_capabilities": context.related_capabilities,
                "related_concepts": context.related_concepts,
            },
            "planning": {
                "goal": result.goal,
                "user_needs": result.user_needs,
                "route": result.route,
                "multiple_intentions_plan": result.multiple_intentions_plan,
            },
            "result": result.to_dict(),
        }
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return path

    @staticmethod
    def _evidence_trace_payload(evidence_bundle: EvidenceBundle | dict[str, Any] | None) -> dict[str, Any]:
        if evidence_bundle is None:
            return {"routes": [], "evidence": []}
        if isinstance(evidence_bundle, EvidenceBundle):
            return evidence_bundle.to_trace_payload()
        return evidence_bundle
