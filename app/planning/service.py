from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from app.knowledge_base.models import AssetSearchResult, EnterpriseAsset
from app.models import KnowledgeRecord, ProcessDefinition, UserTask
from app.planning.models import (
    MultipleIntentionsPlan,
    MultipleIntentionsPlanStep,
    Goal,
    KnownTarget,
    PlanningTrace,
    RouteDecision,
    UserNeed,
)
from app.tools.models import ToolRegistryEntry


@dataclass(frozen=True)
class PlanningService:
    """Classify the user's goal and compose safe runtime plans.

    The service does not invent banking tools. Multiple intentions planning
    means composing already known flows, processes, user tasks, and registered
    tools when the understood ask contains complementary intentions.
    """

    processes: list[ProcessDefinition] = field(default_factory=list)

    def analyze(
        self,
        question: str,
        records: list[KnowledgeRecord],
        registered_tools: list[ToolRegistryEntry],
        question_understanding: Any | None = None,
        asset_search: AssetSearchResult | dict[str, Any] | None = None,
    ) -> PlanningTrace:
        """Classify the ask into needs, route mode, targets, and plan preview."""
        normalized_question = self._normalize(question)
        asset_targets = self._asset_targets(asset_search)
        flow_targets = self._flow_targets(records, normalized_question)
        process_targets = self._process_targets(flow_targets)
        tool_question = (
            self._normalize(self._explanation_text(question))
            if self._asks_how(normalized_question, question_understanding)
            else normalized_question
        )
        tool_targets = self._tool_targets(registered_tools, tool_question)
        question_intent = self._question_intent(normalized_question, question_understanding)
        user_needs = self._identify_user_needs(
            question,
            normalized_question,
            question_intent,
            question_understanding,
            flow_targets,
            process_targets,
            tool_targets,
            asset_targets,
        )
        route = self._route(user_needs, flow_targets, process_targets, tool_targets)
        multiple_intentions_plan = self._compose_multiple_intentions_plan(route, user_needs, records, registered_tools)
        return PlanningTrace(
            goal=self._goal(question, normalized_question, user_needs),
            user_needs=user_needs,
            route=route,
            multiple_intentions_plan=multiple_intentions_plan,
        )

    def _identify_user_needs(
        self,
        question: str,
        normalized_question: str,
        question_intent: str,
        question_understanding: Any | None,
        flow_targets: list[KnownTarget],
        process_targets: list[KnownTarget],
        tool_targets: list[KnownTarget],
        asset_targets: dict[str, list[KnownTarget]],
    ) -> list[UserNeed]:
        needs: list[UserNeed] = []
        if flow_targets and self._wants_execution(normalized_question, question_understanding):
            action = "invoke_known_flow"
            targets = flow_targets[:4]
            if process_targets and self._mentions_process(normalized_question, question_understanding):
                action = "invoke_known_process"
                targets = process_targets[:4]
            needs.append(
                UserNeed(
                    need_id="need_1",
                    kind="execution",
                    text=self._execution_text(question),
                    resolution_action=action,
                    known_targets=targets,
                    reason=self._need_reason(
                        question_understanding,
                        "execution",
                        "The understood ask requests execution and matches known banking execution knowledge.",
                    ),
                )
            )
        if tool_targets or self._asks_how(normalized_question, question_understanding):
            needs.append(
                UserNeed(
                    need_id=f"need_{len(needs) + 1}",
                    kind="explanation",
                    text=self._explanation_text(question),
                    resolution_action="explain_tool",
                    known_targets=tool_targets[:6],
                    reason=self._need_reason(
                        question_understanding,
                        "explanation",
                        "The understood ask requests an explanation of a capability or operation.",
                    ),
                )
            )
        qa_targets = self._unique_targets([*self._qa_targets(normalized_question), *asset_targets.get("qa", [])])
        consultable_rule_targets = asset_targets.get("business_rule", [])
        if question_intent != "none" and qa_targets and (
            not self._asks_how(normalized_question, question_understanding)
            or self._has_operational_question(normalized_question, question_understanding)
        ):
            needs.append(
                UserNeed(
                    need_id=f"need_{len(needs) + 1}",
                    kind="question",
                    text=self._question_text(question),
                    resolution_action="answer_question",
                    known_targets=self._unique_targets([*qa_targets, *consultable_rule_targets])[:6],
                    reason=self._need_reason(
                        question_understanding,
                        "question",
                        f"The understood ask is classified as {question_intent} and matches a known QA topic.",
                    ),
                )
            )
        elif question_intent != "none" and consultable_rule_targets:
            needs.append(
                UserNeed(
                    need_id=f"need_{len(needs) + 1}",
                    kind="question",
                    text=self._question_text(question),
                    resolution_action="answer_question",
                    known_targets=consultable_rule_targets[:6],
                    reason=self._need_reason(
                        question_understanding,
                        "question",
                        f"The understood ask is classified as {question_intent} and matches consultable business rules.",
                    ),
                )
            )
        if not needs:
            needs.append(
                UserNeed(
                    need_id="need_1",
                    kind="unsupported",
                    text=question,
                    resolution_action="reject_unsupported",
                    known_targets=[],
                    reason="No known flow, process, QA topic, or tool explanation matched.",
                )
            )
        return needs

    def _route(
        self,
        user_needs: list[UserNeed],
        flow_targets: list[KnownTarget],
        process_targets: list[KnownTarget],
        tool_targets: list[KnownTarget],
    ) -> RouteDecision:
        supported_needs = [need for need in user_needs if need.kind != "unsupported"]
        all_targets = self._unique_targets(
            target for need in user_needs for target in need.known_targets
        )
        if not supported_needs:
            return RouteDecision(mode="unsupported", reason="No known route can answer or execute this request.")
        if len(supported_needs) == 1 and supported_needs[0].resolution_action == "answer_question":
            primary = supported_needs[0].known_targets[0] if supported_needs[0].known_targets else None
            return RouteDecision(
                mode="known_route",
                reason="A single known QA route can answer the understood question.",
                primary_target=primary,
                targets=all_targets,
            )
        if len(supported_needs) > 1 or len(flow_targets) > 1:
            clarification = len(flow_targets) > 1 and len(supported_needs) == 1
            return RouteDecision(
                mode="clarification" if clarification else "multiple_intentions",
                reason="The goal combines multiple user needs or multiple known targets.",
                targets=all_targets,
                requires_clarification=clarification,
                clarification_question="Which banking operation do you want to continue with?",
            )
        primary = supported_needs[0].known_targets[0] if supported_needs[0].known_targets else None
        if primary is None and tool_targets:
            primary = tool_targets[0]
        if primary is None and process_targets:
            primary = process_targets[0]
        return RouteDecision(
            mode="known_route",
            reason="A single known route can resolve the goal.",
            primary_target=primary,
            targets=all_targets,
        )

    def _compose_multiple_intentions_plan(
        self,
        route: RouteDecision,
        user_needs: list[UserNeed],
        records: list[KnowledgeRecord],
        registered_tools: list[ToolRegistryEntry],
    ) -> MultipleIntentionsPlan:
        if route.mode == "unsupported":
            return MultipleIntentionsPlan(planning_mode="none", validation_errors=["No known planning target matched."])
        if route.mode == "known_route" and route.primary_target is None:
            return MultipleIntentionsPlan(planning_mode="none")

        need_ids_by_flow = {
            target.id: need.need_id
            for need in user_needs
            for target in need.known_targets
            if target.type == "flow"
        }
        tool_names = {entry.tool_id for entry in registered_tools}
        selected_flow_ids = {
            target.id
            for target in route.targets
            if target.type == "flow"
        }
        if route.primary_target and route.primary_target.type == "flow":
            selected_flow_ids.add(route.primary_target.id)

        steps: list[MultipleIntentionsPlanStep] = []
        seen_steps: set[str] = set()
        validation_errors: list[str] = []
        for record in records:
            if record.flow_id not in selected_flow_ids:
                continue
            source_need_id = need_ids_by_flow.get(record.flow_id, "need_1")
            for user_task in record.user_tasks:
                if user_task.task in seen_steps:
                    continue
                seen_steps.add(user_task.task)
                tools = self._task_tools(user_task)
                unknown_tools = [tool for tool in tools if tool not in tool_names]
                if unknown_tools:
                    validation_errors.append(
                        f"Task {user_task.task} references unregistered tools: {', '.join(unknown_tools)}"
                    )
                steps.append(
                    MultipleIntentionsPlanStep(
                        step=user_task.task,
                        type=user_task.type,
                        source_need_ids=[source_need_id],
                        tools=tools,
                        condition=self._condition_for_task(user_task.task),
                        reason=user_task.description or f"Known user task from flow {record.flow_id}.",
                    )
                )
        missing_capabilities = self._missing_capabilities(user_needs, route, selected_flow_ids)
        return MultipleIntentionsPlan(
            planning_mode="multiple_intentions" if route.mode == "multiple_intentions" else "known_route_projection",
            selected_targets=route.targets or ([route.primary_target] if route.primary_target else []),
            steps=steps,
            missing_capabilities=missing_capabilities,
            validation_errors=validation_errors,
        )

    def _goal(self, question: str, normalized_question: str, user_needs: list[UserNeed]) -> Goal:
        if any(need.kind == "execution" for need in user_needs):
            goal_type = "business_goal"
        elif any(need.kind == "explanation" for need in user_needs):
            goal_type = "knowledge_goal"
        elif any(need.kind == "question" for need in user_needs):
            goal_type = "operational_goal"
        else:
            goal_type = "unknown"
        summary = question.strip()
        if "refinanc" in normalized_question and ("cuota" in normalized_question or "pago" in normalized_question):
            summary = "Reducir la cuota del prestamo y entender los pasos relacionados."
        elif "transfer" in normalized_question:
            summary = "Resolver una transferencia de dinero."
        elif "cuenta" in normalized_question:
            summary = "Resolver una necesidad relacionada con cuenta bancaria."
        return Goal(summary=summary, type=goal_type, confidence=0.85 if goal_type != "unknown" else 0.0)

    def _flow_targets(self, records: list[KnowledgeRecord], normalized_question: str) -> list[KnownTarget]:
        targets = []
        for record in records:
            confidence = self._flow_confidence(record, normalized_question)
            if confidence > 0:
                targets.append(
                    KnownTarget(type="flow", id=record.flow_id, label=record.flow_name, confidence=confidence)
                )
        if not targets and len(records) == 1:
            record = records[0]
            targets.append(KnownTarget(type="flow", id=record.flow_id, label=record.flow_name, confidence=record.confidence))
        return sorted(targets, key=lambda target: target.confidence, reverse=True)

    def _process_targets(self, flow_targets: list[KnownTarget]) -> list[KnownTarget]:
        flow_ids = {target.id for target in flow_targets}
        targets = []
        for process in self.processes:
            if flow_ids.intersection(process.related_flow_ids):
                targets.append(
                    KnownTarget(type="process", id=process.process_id, label=process.process_name, confidence=0.82)
                )
        return targets

    def _tool_targets(self, tools: list[ToolRegistryEntry], normalized_question: str) -> list[KnownTarget]:
        if not self._asks_how(normalized_question):
            return []
        targets = []
        for tool in tools:
            haystack = self._normalize(
                " ".join(
                    value
                    for value in [
                        tool.tool_id,
                        tool.operation or "",
                        tool.resource or "",
                        tool.label or "",
                        tool.description or "",
                    ]
                    if value
                )
            )
            if self._semantic_tool_match(normalized_question, haystack):
                targets.append(KnownTarget(type="tool", id=tool.tool_id, label=tool.label, confidence=0.78))
        return targets[:8]

    def _qa_targets(self, normalized_question: str) -> list[KnownTarget]:
        targets = []
        if "pago automatico" in normalized_question or "domicili" in normalized_question:
            targets.append(
                KnownTarget(
                    type="qa",
                    id="qa.automatic_payment_account_required",
                    label="Account requirement for automatic payment",
                    confidence=0.74,
                )
            )
        if "requisit" in normalized_question or "document" in normalized_question:
            targets.append(KnownTarget(type="qa", id="qa.requirements", label="Requirements", confidence=0.7))
        return targets

    def _asset_targets(self, asset_search: AssetSearchResult | dict[str, Any] | None) -> dict[str, list[KnownTarget]]:
        grouped: dict[str, list[KnownTarget]] = {}
        if asset_search is None:
            return grouped
        if isinstance(asset_search, AssetSearchResult):
            assets = asset_search.all_assets()
            for asset in assets:
                grouped.setdefault(asset.asset_type, []).append(self._target_from_asset(asset))
            return grouped
        for key in ("primary_assets", "supporting_assets", "evidence_assets"):
            for asset_id in asset_search.get(key, []) or []:
                asset_type = self._asset_type_from_id(str(asset_id))
                grouped.setdefault(asset_type, []).append(
                    KnownTarget(type=asset_type, id=str(asset_id), label=str(asset_id), confidence=0.72)
                )
        return grouped

    def _target_from_asset(self, asset: EnterpriseAsset) -> KnownTarget:
        target_type = self._asset_type_from_id(asset.asset_id, fallback=asset.asset_type)
        return KnownTarget(
            type=target_type,
            id=asset.asset_id,
            label=asset.name or asset.asset_id,
            confidence=0.76 if asset.is_approved else 0.3,
        )

    def _asset_type_from_id(self, asset_id: str, fallback: str = "document") -> str:
        if asset_id.startswith("qa."):
            return "qa"
        if asset_id.startswith("business_rule."):
            return "business_rule"
        if asset_id.startswith("plan."):
            return "plan"
        if asset_id.startswith("flow."):
            return "flow"
        if asset_id.startswith("process."):
            return "process"
        if asset_id.startswith("tool."):
            return "tool"
        if asset_id.startswith("concept."):
            return "concept"
        return fallback

    def _missing_capabilities(
        self,
        user_needs: list[UserNeed],
        route: RouteDecision,
        selected_flow_ids: set[str],
    ) -> list[str]:
        missing = []
        target_ids = {target.id for target in route.targets}
        if any("pago automatico" in self._normalize(need.text) or "domicili" in self._normalize(need.text) for need in user_needs):
            if not any("payment" in target_id or "loan_payment" in target_id for target_id in target_ids | selected_flow_ids):
                missing.append("configure_automatic_loan_payment")
        return missing

    def _flow_confidence(self, record: KnowledgeRecord, normalized_question: str) -> float:
        flow_id = record.flow_id
        if flow_id == "loan.refinance" and "refinanc" in normalized_question:
            return max(record.confidence, 0.92)
        if flow_id == "savings_account_opening" and (
            "abrir una cuenta" in normalized_question
            or "abrir cuenta" in normalized_question
            or "cuenta para pago" in normalized_question
        ):
            return max(record.confidence, 0.84)
        if flow_id == "loan.payment" and ("pago automatico" in normalized_question or "pagar" in normalized_question):
            return max(record.confidence, 0.82)
        if flow_id == "money.transfer" and "transfer" in normalized_question:
            return max(record.confidence, 0.88)
        if flow_id in {"loan.request", "loan_application_process"} and (
            "solicitar prestamo" in normalized_question
            or "pedir prestamo" in normalized_question
            or "prestamo nuevo" in normalized_question
        ):
            return max(record.confidence, 0.86)
        for utterance in record.utterances:
            normalized_utterance = self._normalize(utterance)
            if normalized_utterance and normalized_utterance in normalized_question:
                return max(record.confidence, 0.8)
        return 0.0

    def _task_tools(self, user_task: UserTask) -> list[str]:
        values = []
        seen = set()
        for tool in user_task.tools:
            if tool.tool_id not in seen:
                values.append(tool.tool_id)
                seen.add(tool.tool_id)
        return values

    def _condition_for_task(self, task: str) -> str | None:
        if "open" in task and "account" in task:
            return "Only if the customer does not already have an eligible account."
        return None

    def _asks_question(self, normalized_question: str) -> bool:
        markers = ("?", "que ", "cual ", "cuando ", "dime si", "necesito", "conviene", "requisit")
        return any(marker in normalized_question for marker in markers)

    def _question_intent(self, normalized_question: str, question_understanding: Any | None = None) -> str:
        ask_posture = self._ask_posture(question_understanding)
        if ask_posture in {"doubt", "consultation", "problem"}:
            return ask_posture
        if ask_posture == "mixed" and self._hint_enabled(question_understanding, "needs_answer"):
            return "consultation"
        if self._has_problem_signal(normalized_question):
            return "problem"
        if self._has_doubt_signal(normalized_question):
            return "doubt"
        if self._asks_question(normalized_question):
            return "consultation"
        return "none"

    def _has_problem_signal(self, normalized_question: str) -> bool:
        markers = (
            "tengo un problema",
            "no puedo",
            "no me deja",
            "fallo",
            "error",
            "rechaz",
            "no funciona",
            "no tengo dinero",
        )
        return any(marker in normalized_question for marker in markers)

    def _has_doubt_signal(self, normalized_question: str) -> bool:
        markers = (
            "tengo duda",
            "duda",
            "consulta",
            "consultar",
            "dime si",
            "necesito saber",
            "necesito una cuenta",
            "es necesario",
            "tengo que",
            "debo",
            "puedo",
            "conviene",
        )
        return any(marker in normalized_question for marker in markers)

    def _asks_how(self, normalized_question: str, question_understanding: Any | None = None) -> bool:
        if self._hint_enabled(question_understanding, "needs_tool_explanation"):
            return True
        if self._ask_posture(question_understanding) == "tool_explanation":
            return True
        markers = ("como ", "explica", "explicame", "funciona", "calculan", "calcula")
        return any(marker in normalized_question for marker in markers)

    def _has_operational_question(self, normalized_question: str, question_understanding: Any | None = None) -> bool:
        if self._hint_enabled(question_understanding, "needs_answer"):
            return True
        if self._has_inferred_need(question_understanding, "question"):
            return True
        markers = ("dime si", "necesito abrir", "conviene", "requisit", "pago automatico")
        return any(marker in normalized_question for marker in markers)

    def _mentions_process(self, normalized_question: str, question_understanding: Any | None = None) -> bool:
        return (
            self._hint_enabled(question_understanding, "needs_process")
            or "proceso" in normalized_question
            or "ejecut" in normalized_question
        )

    def _wants_execution(self, normalized_question: str, question_understanding: Any | None = None) -> bool:
        ask_posture = self._ask_posture(question_understanding)
        if ask_posture in {"execution_request", "mixed"} and self._hint_enabled(question_understanding, "needs_flow"):
            return True
        if self._has_inferred_need(question_understanding, "execution"):
            return True
        markers = (
            "quiero",
            "necesito hacer",
            "solicito",
            "abrir",
            "transferir",
            "refinanciar",
            "pagar",
            "depositar",
            "crear",
        )
        return any(marker in normalized_question for marker in markers)

    def _ask_posture(self, question_understanding: Any | None) -> str:
        value = getattr(question_understanding, "ask_posture", None)
        return self._normalize(str(value)) if value else "unknown"

    def _hint_enabled(self, question_understanding: Any | None, name: str) -> bool:
        hints = getattr(question_understanding, "routing_hints", None)
        return isinstance(hints, dict) and hints.get(name) is True

    def _has_inferred_need(self, question_understanding: Any | None, kind: str) -> bool:
        needs = getattr(question_understanding, "inferred_needs", None)
        if not isinstance(needs, list):
            return False
        return any(isinstance(need, dict) and need.get("kind") == kind for need in needs)

    def _need_reason(self, question_understanding: Any | None, kind: str, fallback: str) -> str:
        needs = getattr(question_understanding, "inferred_needs", None)
        if isinstance(needs, list):
            for need in needs:
                if isinstance(need, dict) and need.get("kind") == kind and need.get("reason"):
                    return str(need["reason"])
        return fallback

    def _execution_text(self, question: str) -> str:
        return self._best_fragment(question, ("quiero", "necesito", "solicito", "hacer"))

    def _explanation_text(self, question: str) -> str:
        return self._best_fragment(question, ("como", "explica", "funciona", "calcul"))

    def _question_text(self, question: str) -> str:
        return self._best_fragment(question, ("dime", "necesito", "conviene", "que"))

    def _best_fragment(self, question: str, starts: tuple[str, ...]) -> str:
        parts = re.split(r",|\by\b|\bpero\b", question, flags=re.IGNORECASE)
        for part in parts:
            normalized = self._normalize(part)
            if any(start in normalized for start in starts):
                return part.strip()
        return question.strip()

    def _meaningful_tokens(self, value: str) -> list[str]:
        stop = {"como", "que", "para", "por", "con", "una", "uno", "las", "los", "del", "mis", "mi"}
        return [token for token in re.split(r"\W+", value) if len(token) > 3 and token not in stop]

    def _semantic_tool_match(self, normalized_question: str, normalized_tool: str) -> bool:
        score = 0
        pairs = {
            "condicion": "condition",
            "cuota": "payment",
            "prestamo": "loan",
            "calcula": "calculate",
            "calculan": "calculate",
            "cuenta": "account",
            "pago": "payment",
        }
        for question_token, tool_token in pairs.items():
            if question_token in normalized_question and tool_token in normalized_tool:
                score += 1
        if "condicion" in normalized_question and "loan.conditions.calculate" in normalized_tool:
            return True
        return score >= 2

    def _unique_targets(self, targets) -> list[KnownTarget]:
        values = []
        seen = set()
        for target in targets:
            key = (target.type, target.id)
            if key not in seen:
                values.append(target)
                seen.add(key)
        return values

    def _normalize(self, value: str) -> str:
        without_accents = unicodedata.normalize("NFKD", value)
        ascii_value = without_accents.encode("ascii", "ignore").decode("ascii")
        return ascii_value.lower()
