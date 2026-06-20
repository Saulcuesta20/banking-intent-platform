from __future__ import annotations

from typing import Any

from app.knowledge_base.models import KnowledgeSourceRoute


class KnowledgeSourceRouter:
    """Choose knowledge sources after the ask/goal router understands the need."""

    def route(
        self,
        *,
        question: str,
        search_terms: list[str],
        question_understanding: dict[str, Any] | None = None,
        asset_search: dict[str, Any] | None = None,
    ) -> list[KnowledgeSourceRoute]:
        """Choose one or more knowledge sources/views for an understood ask."""
        normalized = " ".join([question, *search_terms]).lower()
        routing_hints = self._routing_hints(question_understanding)
        routes: list[KnowledgeSourceRoute] = []

        if routing_hints.get("needs_answer") or self._has_asset_matches(asset_search, "primary_assets"):
            routes.append(
                KnowledgeSourceRoute(
                    source="qa",
                    views=["repository", "vector"],
                    asset_types=["qa"],
                    reason="The ask router identified a direct question or QA target.",
                )
            )
        if routing_hints.get("needs_flow") or routing_hints.get("needs_process"):
            routes.append(
                KnowledgeSourceRoute(
                    source="process_flows",
                    views=["graph", "repository"],
                    asset_types=["flow", "process", "plan"],
                    reason="The ask router identified a flow, process, or operational path need.",
                )
            )
        if self._mentions_rules(normalized) or self._has_asset_matches(asset_search, "supporting_assets"):
            routes.append(
                KnowledgeSourceRoute(
                    source="rules_policies",
                    views=["repository", "document", "graph"],
                    asset_types=["business_rule", "rule", "policy", "document"],
                    reason="The question or matched assets require rules, policies, or document evidence.",
                )
            )
        if self._mentions_tools(normalized) or routing_hints.get("needs_tool_explanation"):
            routes.append(
                KnowledgeSourceRoute(
                    source="tools_apis",
                    views=["repository", "graph", "external_api"],
                    asset_types=["tool", "capability"],
                    reason="The ask needs tool, API, or backend/frontend capability knowledge.",
                )
            )
        if self._mentions_configuration(normalized):
            routes.append(
                KnowledgeSourceRoute(
                    source="configurations",
                    views=["repository", "document"],
                    asset_types=["configuration"],
                    reason="The question mentions configuration or environment-specific behavior.",
                )
            )
        if search_terms:
            routes.append(
                KnowledgeSourceRoute(
                    source="entities",
                    views=["graph", "repository"],
                    asset_types=["entity", "concept"],
                    reason="Search terms and extracted entities expand retrieval through synonyms and relationships.",
                )
            )

        return self._deduplicate(routes)

    @staticmethod
    def _routing_hints(question_understanding: dict[str, Any] | None) -> dict[str, Any]:
        if not isinstance(question_understanding, dict):
            return {}
        hints = question_understanding.get("routing_hints")
        return hints if isinstance(hints, dict) else {}

    @staticmethod
    def _has_asset_matches(asset_search: dict[str, Any] | None, key: str) -> bool:
        return bool(asset_search and asset_search.get("enabled") and asset_search.get(key))

    @staticmethod
    def _mentions_rules(text: str) -> bool:
        return any(token in text for token in ["regla", "policy", "politica", "política", "cumpl", "aml", "limite", "límite"])

    @staticmethod
    def _mentions_tools(text: str) -> bool:
        return any(token in text for token in ["tool", "api", "acción", "accion", "backend", "frontend", "boton", "botón"])

    @staticmethod
    def _mentions_configuration(text: str) -> bool:
        return any(token in text for token in ["config", "parametro", "parámetro", "yaml", "setting"])

    @staticmethod
    def _deduplicate(routes: list[KnowledgeSourceRoute]) -> list[KnowledgeSourceRoute]:
        deduped: list[KnowledgeSourceRoute] = []
        seen: set[str] = set()
        for route in routes:
            if route.source in seen:
                continue
            seen.add(route.source)
            deduped.append(route)
        return deduped
