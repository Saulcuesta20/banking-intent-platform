from __future__ import annotations

import csv
import difflib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from app.ingestion.llm_flow_loader import CorpusDocument, LLMClient
from app.ingestion.relation_normalization import RelationNormalizationService
from app.knowledge_base.models import AssetRelation, EnterpriseAsset
from app.knowledge_base.registry import EnterpriseAssetRegistry
from app.knowledge_base.repository import EnterpriseAssetRepository
from app.knowledge_base.vocabulary import ConceptVocabulary
from app.models import KnowledgeRecord

GENERIC_STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "by",
    "de",
    "del",
    "el",
    "en",
    "for",
    "from",
    "in",
    "la",
    "las",
    "los",
    "of",
    "or",
    "para",
    "por",
    "the",
    "to",
    "un",
    "una",
    "y",
}

GENERIC_ACTION_WORDS = {
    "actualiza",
    "affects",
    "aplica",
    "apply",
    "blocks",
    "bloquea",
    "causa",
    "causes",
    "captures",
    "completa",
    "contains",
    "contiene",
    "create",
    "creates",
    "crea",
    "ejecuta",
    "enables",
    "exige",
    "genera",
    "generate",
    "generates",
    "hace",
    "habilita",
    "impacts",
    "impacta",
    "impide",
    "includes",
    "incluye",
    "prevents",
    "provoca",
    "receives",
    "recibe",
    "records",
    "registra",
    "requests",
    "requiere",
    "requires",
    "respalda",
    "supports",
    "soporta",
    "updates",
    "uses",
    "utiliza",
    "valida",
    "validate",
    "validates",
}


@dataclass(frozen=True)
class RelationPattern:
    relation_type: str
    family: str
    phrases: list[str] = field(default_factory=list)
    source_asset_types: list[str] = field(default_factory=list)
    target_asset_types: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RelationHint:
    relation_type: str
    family: str
    phrase: str
    sentence: str


@dataclass(frozen=True)
class AssetReferenceTarget:
    asset_id: str
    asset_type: str
    name: str
    terms: tuple[str, ...] = ()


@dataclass
class AssetCandidate:
    asset_type: str
    name: str
    description: str = ""
    text: str = ""
    status: str = "approved"
    owner: str | None = None
    tags: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    source_refs: list[str] = field(default_factory=list)
    relations: list[AssetRelation] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)
    evidence: list[dict[str, Any]] = field(default_factory=list)


class BasicTextAnalyzer:
    def sentences(self, text: str) -> list[str]:
        if not text.strip():
            return []
        return [part.strip() for part in re.split(r"(?<=[.!?])\s+|\n+", text) if part.strip()]

    def noun_phrases(self, text: str) -> list[str]:
        if not text.strip():
            return []
        return self._fallback_noun_phrases(text)

    @staticmethod
    def _fallback_noun_phrases(text: str) -> list[str]:
        phrases: list[str] = []
        for match in re.finditer(r"[A-Za-zÁÉÍÓÚÑáéíóúñ][A-Za-zÁÉÍÓÚÑáéíóúñ0-9._-]*(?:\s+[A-Za-zÁÉÍÓÚÑáéíóúñ][A-Za-zÁÉÍÓÚÑáéíóúñ0-9._-]*){0,3}", text):
            phrase = " ".join(match.group(0).strip().split())
            if BasicTextAnalyzer._looks_like_generic_phrase(phrase):
                phrases.append(phrase)
        return _dedupe_preserve(phrases)

    @staticmethod
    def _looks_like_generic_phrase(text: str) -> bool:
        tokens = [token.casefold() for token in text.split()]
        if not tokens or len(tokens) > 4:
            return False
        if all(token in GENERIC_STOPWORDS for token in tokens):
            return False
        if any(token in GENERIC_ACTION_WORDS for token in tokens):
            return False
        if not any(any(char.isalpha() for char in token) for token in tokens):
            return False
        return True


class RelationPatternCatalog:
    def __init__(self, path: Path):
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        relation_types = raw.get("relation_types") or {}
        self.patterns: list[RelationPattern] = [
            RelationPattern(
                relation_type=name,
                family=str(config.get("family") or "semantic"),
                phrases=[str(value) for value in config.get("phrases", [])],
                source_asset_types=[str(value) for value in config.get("source_asset_types", [])],
                target_asset_types=[str(value) for value in config.get("target_asset_types", [])],
            )
            for name, config in relation_types.items()
            if isinstance(config, dict)
        ]

    def detect(self, text: str) -> list[RelationHint]:
        hints: list[RelationHint] = []
        normalized = text.casefold()
        for pattern in self.patterns:
            for phrase in pattern.phrases:
                escaped = re.escape(phrase.casefold())
                regex = rf"(?<![a-z0-9_]){escaped}(?![a-z0-9_])"
                if re.search(regex, normalized):
                    hints.append(
                        RelationHint(
                            relation_type=pattern.relation_type,
                            family=pattern.family,
                            phrase=phrase,
                            sentence=text.strip(),
                        )
                    )
        return hints


class AssetCanonicalizer:
    def __init__(
        self,
        *,
        registry: EnterpriseAssetRegistry,
        repository: EnterpriseAssetRepository | None = None,
        vocabulary: ConceptVocabulary | None = None,
    ):
        self.registry = registry
        self.repository = repository or EnterpriseAssetRepository([])
        self.vocabulary = vocabulary or ConceptVocabulary()

    def normalize(self, candidates: list[AssetCandidate]) -> list[EnterpriseAsset]:
        grouped: dict[tuple[str, str], AssetCandidate] = {}
        for candidate in candidates:
            normalized_name = self._normalized_name(candidate.name)
            key = (candidate.asset_type, normalized_name)
            existing = grouped.get(key)
            if existing is None:
                candidate.aliases = self._sanitize_aliases(candidate.asset_type, candidate.aliases, candidate.name)
                grouped[key] = candidate
                continue
            existing.aliases = self._sanitize_aliases(
                candidate.asset_type,
                [*existing.aliases, *candidate.aliases],
                existing.name,
            )
            existing.tags = _dedupe_preserve([*existing.tags, *candidate.tags])
            existing.source_refs = _dedupe_preserve([*existing.source_refs, *candidate.source_refs])
            existing.relations = _dedupe_relations([*existing.relations, *candidate.relations])
            existing.payload.update(candidate.payload)
            if len(candidate.text) > len(existing.text):
                existing.text = candidate.text
            if len(candidate.description) > len(existing.description):
                existing.description = candidate.description

        assets: list[EnterpriseAsset] = []
        for candidate in grouped.values():
            aligned = self._align(candidate)
            canonical_name = aligned.name
            aliases = self._sanitize_aliases(candidate.asset_type, candidate.aliases, canonical_name)
            payload = {
                **candidate.payload,
                "canonical_name": canonical_name,
                "normalized_name": self._normalized_name(canonical_name),
                "aliases": aliases,
                "alignment": {
                    "matched_existing_asset_id": aligned.asset_id if aligned.asset_id != self._asset_id(candidate) else None,
                    "match_strategy": candidate.payload.get("match_strategy", "exact_or_generated"),
                },
            }
            assets.append(
                EnterpriseAsset(
                    asset_id=aligned.asset_id,
                    asset_type=candidate.asset_type,
                    name=canonical_name,
                    version=aligned.version,
                    status=candidate.status,
                    owner=candidate.owner or self.registry.owner_kb_for(candidate.asset_type),
                    description=candidate.description or aligned.description,
                    text=candidate.text or aligned.text,
                    tags=_dedupe_preserve([*aligned.tags, *candidate.tags]),
                    source_refs=_dedupe_preserve([*aligned.source_refs, *candidate.source_refs]),
                    relations=_dedupe_relations([*aligned.relations, *candidate.relations]),
                    payload=payload,
                )
            )
        return sorted(assets, key=lambda asset: (asset.asset_type, asset.asset_id))

    def _align(self, candidate: AssetCandidate) -> EnterpriseAsset:
        requested_id = self._asset_id(candidate)
        existing = self.repository.get(requested_id)
        if existing is not None:
            candidate.payload["match_strategy"] = "asset_id"
            return existing
        normalized_name = self._normalized_name(candidate.name)
        best_match: EnterpriseAsset | None = None
        best_score = 0.0
        for asset in self.repository.list_assets(candidate.asset_type, approved_only=False):
            other_name = self._normalized_name(asset.name or asset.asset_id)
            score = difflib.SequenceMatcher(a=normalized_name, b=other_name).ratio()
            if score > best_score:
                best_score = score
                best_match = asset
        if best_match is not None and best_score >= 0.93:
            candidate.payload["match_strategy"] = "fuzzy_name"
            return best_match
        candidate.payload["match_strategy"] = "generated"
        return EnterpriseAsset(
            asset_id=requested_id,
            asset_type=candidate.asset_type,
            name=candidate.name,
            version="1.0.0",
            status=candidate.status,  # type: ignore[arg-type]
            owner=candidate.owner or self.registry.owner_kb_for(candidate.asset_type),
        )

    def _asset_id(self, candidate: AssetCandidate) -> str:
        asset_type = "entity" if candidate.asset_type == "concept" else candidate.asset_type
        name = candidate.name
        payload = candidate.payload if isinstance(candidate.payload, dict) else {}
        canonical_key = ""
        if asset_type in {"flow", "process", "plan", "ruleset", "asset_set"}:
            canonical_key = str(
                payload.get("transaction_id")
                or payload.get("flow_id")
                or payload.get("process_id")
                or payload.get("ruleset_id")
                or payload.get("asset_set_id")
                or ""
            ).strip()
        if asset_type == "entity":
            normalized = self.vocabulary.normalize_term(name).canonical
        elif canonical_key:
            normalized = canonical_key
        else:
            normalized = _slug(name).replace("_", ".") if asset_type in {"flow", "process"} else _slug(name)
        return f"{asset_type}.{normalized}"

    @staticmethod
    def _normalized_name(value: str) -> str:
        return " ".join(str(value).casefold().replace("_", " ").split())

    def _sanitize_aliases(self, asset_type: str, aliases: list[str], canonical_name: str) -> list[str]:
        reserved = {"true", "false", "none", "null", "yes", "no", "n/a"}
        canonical_normalized = self._normalized_name(canonical_name)
        cleaned: list[str] = []
        seen: set[str] = set()
        for alias in aliases:
            if not isinstance(alias, str):
                continue
            text = " ".join(alias.strip().split())
            if not text:
                continue
            normalized = self._normalized_name(text)
            if normalized in reserved or normalized == canonical_normalized:
                continue
            if not any(char.isalpha() for char in text):
                continue
            if asset_type != "entity" and len(text.split()) > 5:
                continue
            if asset_type in {"rule", "plan", "process", "flow", "causality", "qa", "document"} and len(text.split()) > 3:
                continue
            if asset_type == "rule" and any(token in normalized for token in (" then ", " when ", " if ")):
                continue
            if normalized in seen:
                continue
            seen.add(normalized)
            cleaned.append(text)
        return cleaned


class CanonicalAssetPipeline:
    def __init__(
        self,
        *,
        registry: EnterpriseAssetRegistry,
        relation_pattern_path: Path,
        repository: EnterpriseAssetRepository | None = None,
        vocabulary: ConceptVocabulary | None = None,
        llm_client: LLMClient | None = None,
        relation_normalizer: RelationNormalizationService | None = None,
    ):
        self.registry = registry
        self.repository = repository or EnterpriseAssetRepository([])
        self.vocabulary = vocabulary or ConceptVocabulary()
        self.llm_client = llm_client
        self.relation_normalizer = relation_normalizer
        self.relation_patterns = RelationPatternCatalog(relation_pattern_path)
        self.text_analyzer = BasicTextAnalyzer()
        self.canonicalizer = AssetCanonicalizer(
            registry=registry,
            repository=self.repository,
            vocabulary=self.vocabulary,
        )

    def run(
        self,
        *,
        documents: list[CorpusDocument],
        extraction: dict[str, Any],
        records: list[KnowledgeRecord],
    ) -> list[EnterpriseAsset]:
        candidates = self.extract_candidates(documents=documents, extraction=extraction, records=records)
        candidates = self.enrich_relations(candidates, records=records)
        candidates = self._group_transaction_assets(candidates)
        return self.canonicalizer.normalize(candidates)

    def extract_candidates(
        self,
        *,
        documents: list[CorpusDocument],
        extraction: dict[str, Any],
        records: list[KnowledgeRecord],
    ) -> list[AssetCandidate]:
        candidates: list[AssetCandidate] = []
        candidates.extend(self._document_candidates(documents))
        llm_assets = self._llm_asset_candidates(documents)
        candidates.extend(llm_assets.get("entity", []))
        candidates.extend(self._tool_candidates(extraction.get("tool_registry", []), documents))
        candidates.extend(self._user_task_candidates(extraction.get("user_tasks", []), documents))
        candidates.extend(self._flow_candidates(records, documents))
        candidates.extend(llm_assets.get("business_rule", []) or self._rule_candidates(documents, records))
        candidates.extend(llm_assets.get("process", []) or self._process_candidates(documents, records))
        candidates.extend(llm_assets.get("plan", []) or self._plan_candidates(documents, records))
        candidates.extend(llm_assets.get("qa", []) or self._qa_candidates(documents, records))
        candidates.extend(llm_assets.get("causality", []) or self._causality_candidates(documents, records))
        if not llm_assets.get("entity"):
            candidates.extend(self._entity_candidates(documents, records))
        return candidates

    def enrich_relations(self, candidates: list[AssetCandidate], *, records: list[KnowledgeRecord]) -> list[AssetCandidate]:
        entity_map = {
            _slug(candidate.name): candidate
            for candidate in candidates
            if candidate.asset_type == "entity"
        }
        reference_targets = self._build_reference_targets(candidates)
        flow_ids = {record.flow_id: record for record in records}
        for candidate in candidates:
            combined_text = "\n".join(part for part in [candidate.name, candidate.description, candidate.text] if part)
            hints = []
            for sentence in self.text_analyzer.sentences(combined_text):
                hints.extend(self.relation_patterns.detect(sentence))
            candidate.payload["relation_hints"] = [
                {"type": hint.relation_type, "family": hint.family, "phrase": hint.phrase, "sentence": hint.sentence}
                for hint in hints
            ]
            if candidate.asset_type in {"process", "flow", "plan", "qa", "business_rule"}:
                for key, entity in entity_map.items():
                    if key and key.replace("_", " ") in combined_text.casefold():
                        candidate.relations.append(
                            AssetRelation(type="uses_entity", target_asset_id=f"entity.{self.vocabulary.normalize_term(entity.name).canonical}")
                        )
            if candidate.asset_type == "causality":
                self._enrich_causality_candidate(candidate, entity_map, flow_ids, reference_targets)
            candidate.relations = self._normalize_relations(candidate)
            candidate.relations = _dedupe_relations(candidate.relations)
        return candidates

    def _llm_asset_candidates(self, documents: list[CorpusDocument]) -> dict[str, list[AssetCandidate]]:
        if self.llm_client is None:
            return {}
        try:
            result = self.llm_client.complete_json(self._asset_system_prompt(), self._asset_user_content(documents))
        except Exception:
            return {}
        return {
            "entity": self._entity_candidates_from_llm(result.get("entities", [])),
            "business_rule": self._rule_candidates_from_llm(result.get("business_rules", [])),
            "process": self._process_candidates_from_llm(result.get("processes", [])),
            "plan": self._plan_candidates_from_llm(result.get("plans", [])),
            "qa": self._qa_candidates_from_llm(result.get("qas", [])),
            "causality": self._causality_candidates_from_llm(result.get("causalities", [])),
        }

    def _document_candidates(self, documents: list[CorpusDocument]) -> list[AssetCandidate]:
        values: list[AssetCandidate] = []
        for index, document in enumerate(documents, start=1):
            values.append(
                AssetCandidate(
                    asset_type="document",
                    name=document.path.name,
                    description=f"Raw corpus document loaded from {document.path}",
                    text=document.text,
                    tags=[document.kind, document.path.suffix.lower().lstrip(".")],
                    source_refs=[str(document.path)],
                    payload={"path": str(document.path), "kind": document.kind, "sequence": index},
                )
            )
        return values

    def _entity_candidates_from_llm(self, items: list[dict[str, Any]]) -> list[AssetCandidate]:
        values: list[AssetCandidate] = []
        for item in items:
            name = str(item.get("name") or "").strip()
            if not name or not self._is_entity_candidate(name, source="llm"):
                continue
            aliases = [str(alias).strip() for alias in item.get("aliases", []) if str(alias).strip()]
            description = str(item.get("description") or item.get("definition") or "").strip()
            evidence = [str(value).strip() for value in item.get("evidence", []) if str(value).strip()]
            values.append(
                AssetCandidate(
                    asset_type="entity",
                    name=name,
                    description=description,
                    text="\n".join(evidence),
                    aliases=aliases,
                    payload={"aliases": aliases, "definition": description, "inferred_from": "llm_asset_extraction"},
                )
            )
        return values

    def _rule_candidates_from_llm(self, items: list[dict[str, Any]]) -> list[AssetCandidate]:
        values: list[AssetCandidate] = []
        for item in items:
            name = str(item.get("name") or "").strip()
            rule_text = str(item.get("rule_text") or item.get("description") or "").strip()
            if not name or not rule_text:
                continue
            conditions = [str(value).strip() for value in item.get("conditions", []) if str(value).strip()]
            consequences = [str(value).strip() for value in item.get("consequences", []) if str(value).strip()]
            if not conditions and not consequences:
                inferred = _extract_rule_structure(rule_text)
                conditions = inferred["conditions"]
                consequences = inferred["consequences"]
            transaction_id = _normalize_transaction_id(item.get("transaction_id"))
            ruleset_name = str(item.get("ruleset_name") or "").strip()
            values.append(
                AssetCandidate(
                    asset_type="business_rule",
                    name=name,
                    description=_first_sentence(rule_text),
                    text=rule_text,
                    tags=["business_rule"],
                    payload={
                        "rule_text": rule_text,
                        "source_section": "LLMAssetExtraction",
                        "conditions": conditions,
                        "consequences": consequences,
                        "transaction_id": transaction_id,
                        "ruleset_name": ruleset_name,
                    },
                )
            )
        return values

    def _process_candidates_from_llm(self, items: list[dict[str, Any]]) -> list[AssetCandidate]:
        values: list[AssetCandidate] = []
        for item in items:
            name = str(item.get("name") or "").strip()
            description = str(item.get("description") or "").strip()
            steps = [str(step).strip() for step in item.get("steps", []) if str(step).strip()]
            if not name:
                continue
            values.append(
                AssetCandidate(
                    asset_type="process",
                    name=name,
                    description=description or _first_sentence(" ".join(steps)),
                    text="\n".join(steps),
                    tags=["process_fragment"],
                    payload={
                        "steps_text": "\n".join(steps),
                        "source_section": "LLMAssetExtraction",
                        "transaction_id": _normalize_transaction_id(item.get("transaction_id")),
                    },
                )
            )
        return values

    def _plan_candidates_from_llm(self, items: list[dict[str, Any]]) -> list[AssetCandidate]:
        values: list[AssetCandidate] = []
        for item in items:
            name = str(item.get("name") or "").strip()
            description = str(item.get("description") or item.get("objective") or "").strip()
            steps = [str(step).strip() for step in item.get("steps", []) if str(step).strip()]
            if not name:
                continue
            values.append(
                AssetCandidate(
                    asset_type="plan",
                    name=name,
                    description=description or _first_sentence(" ".join(steps)),
                    text="\n".join(steps),
                    tags=["orchestration_plan"],
                    payload={
                        "steps": steps,
                        "plan_text": "\n".join(steps),
                        "source_section": "LLMAssetExtraction",
                        "transaction_id": _normalize_transaction_id(item.get("transaction_id")),
                    },
                )
            )
        return values

    def _qa_candidates_from_llm(self, items: list[dict[str, Any]]) -> list[AssetCandidate]:
        values: list[AssetCandidate] = []
        for item in items:
            question = str(item.get("question") or "").strip()
            answer = str(item.get("answer") or item.get("description") or "").strip()
            if not question:
                continue
            values.append(
                AssetCandidate(
                    asset_type="qa",
                    name=question.rstrip("?") + "?",
                    description=_first_sentence(answer) if answer else question,
                    text=answer,
                    tags=["qa"],
                    payload={
                        "question": question.rstrip("?") + "?",
                        "answer": answer,
                        "transaction_id": _normalize_transaction_id(item.get("transaction_id")),
                    },
                )
            )
        return values

    def _causality_candidates_from_llm(self, items: list[dict[str, Any]]) -> list[AssetCandidate]:
        values: list[AssetCandidate] = []
        seen: set[str] = set()
        for item in items:
            cause = str(item.get("cause_text") or "").strip()
            effect = str(item.get("effect_text") or "").strip()
            relation_kind = str(item.get("relation_kind") or "causes").strip() or "causes"
            statement = str(item.get("statement") or item.get("description") or "").strip()
            if not cause or not effect:
                continue
            key = f"{_slug(cause)}::{relation_kind}::{_slug(effect)}"
            if key in seen:
                continue
            seen.add(key)
            values.append(
                AssetCandidate(
                    asset_type="causality",
                    name=statement or f"{cause} {relation_kind} {effect}",
                    description=statement or f"{cause} {relation_kind} {effect}",
                    text=statement or f"{cause} {relation_kind} {effect}",
                    tags=["causality", relation_kind],
                    payload={
                        "cause_text": cause,
                        "effect_text": effect,
                        "relation_kind": relation_kind,
                        "sentence": statement or f"{cause} {relation_kind} {effect}",
                        "inferred_from": "llm_asset_extraction",
                        "transaction_id": _normalize_transaction_id(item.get("transaction_id")),
                    },
                )
            )
        return values

    def _entity_candidates(self, documents: list[CorpusDocument], records: list[KnowledgeRecord]) -> list[AssetCandidate]:
        candidates: dict[str, AssetCandidate] = {}
        for record in records:
            for concept in record.concepts:
                normalized = self.vocabulary.normalize_term(concept)
                key = normalized.canonical
                candidate = candidates.setdefault(
                    key,
                    AssetCandidate(
                        asset_type="entity",
                        name=concept,
                        description=f"Business entity aligned from corpus meaning: {concept}",
                        aliases=normalized.aliases,
                        payload={"aliases": normalized.aliases},
                    ),
                )
                candidate.aliases = _dedupe_preserve([*candidate.aliases, *record.concept_aliases.get(concept, [])])
                candidate.tags = _dedupe_preserve([*candidate.tags, record.intent])
                candidate.source_refs = _dedupe_preserve([*candidate.source_refs, *record.metadata.get("source_files", [])])
        glossary_rows = self._glossary_rows(documents)
        for row in glossary_rows:
            term = row.get("term") or row.get("entity") or ""
            definition = row.get("definition") or row.get("description") or ""
            if not term:
                continue
            normalized = self.vocabulary.normalize_term(term)
            candidate = candidates.setdefault(
                normalized.canonical,
                AssetCandidate(
                    asset_type="entity",
                    name=term,
                    description=definition or f"Business entity inferred from glossary: {term}",
                    aliases=normalized.aliases,
                    payload={"aliases": normalized.aliases},
                ),
            )
            candidate.aliases = _dedupe_preserve([*candidate.aliases, *normalized.aliases])
            if definition:
                candidate.text = f"{candidate.text}\n{definition}".strip()
            category = row.get("category")
            if category:
                candidate.tags.append(str(category))
        for document in documents:
            for item in _section_items(document.text, {"entities"}):
                for phrase in self._entity_mentions_from_text(item):
                    if not self._is_entity_candidate(phrase, source="section"):
                        continue
                    normalized = self.vocabulary.normalize_term(phrase)
                    candidates.setdefault(
                        normalized.canonical,
                        AssetCandidate(
                            asset_type="entity",
                            name=phrase,
                            description=f"Business entity listed in corpus section: {item}",
                            aliases=normalized.aliases,
                            source_refs=[str(document.path)],
                            payload={"aliases": normalized.aliases, "inferred_from": "section_entities"},
                        ),
                    )
        return list(candidates.values())

    def _tool_candidates(self, tools: list[dict[str, Any]], documents: list[CorpusDocument]) -> list[AssetCandidate]:
        values = [
            AssetCandidate(
                asset_type="tool",
                name=str(tool.get("label") or tool.get("tool_id") or ""),
                description=str(tool.get("description") or ""),
                tags=[str(tool.get("tool_type") or ""), str(tool.get("operation") or ""), str(tool.get("resource") or "")],
                payload=tool,
            )
            for tool in tools
            if tool.get("tool_id")
        ]
        for document in documents:
            for item in _section_items(document.text, {"tools"}):
                values.append(
                    AssetCandidate(
                        asset_type="tool",
                        name=_tool_name_from_text(item),
                        description=item,
                        text=item,
                        source_refs=[str(document.path)],
                        payload={"description": item, "tool_id": _slug(_tool_name_from_text(item)).replace("_", ".")},
                    )
                )
        return values

    def _user_task_candidates(self, user_tasks: list[dict[str, Any]], documents: list[CorpusDocument]) -> list[AssetCandidate]:
        candidates: list[AssetCandidate] = []
        for task in user_tasks:
            relations = [
                AssetRelation(type="invokes_tool", target_asset_id=f"tool.{_slug(tool['tool_id'])}")
                for tool in task.get("tools", [])
                if tool.get("tool_id")
            ]
            candidates.append(
                AssetCandidate(
                    asset_type="user_task",
                    name=str(task.get("name") or task.get("user_task_id") or ""),
                    description=str(task.get("description") or ""),
                    relations=relations,
                    payload=task,
                )
            )
        for document in documents:
            for item in _section_items(document.text, {"user tasks"}):
                candidates.append(
                    AssetCandidate(
                        asset_type="user_task",
                        name=_task_name_from_text(item),
                        description=item,
                        text=item,
                        source_refs=[str(document.path)],
                        payload={"description": item},
                    )
                )
        return candidates

    def _flow_candidates(self, records: list[KnowledgeRecord], documents: list[CorpusDocument]) -> list[AssetCandidate]:
        values: list[AssetCandidate] = []
        for record in records:
            relations = [
                AssetRelation(type="decomposes_to_user_task", target_asset_id=f"user_task.{task.user_task_id or task.task}")
                for task in record.user_tasks
            ]
            values.append(
                AssetCandidate(
                    asset_type="flow",
                    name=record.flow_name,
                    description=record.explanation,
                    text="\n".join([record.explanation, *record.utterances]),
                    tags=[*record.concepts, record.intent],
                    source_refs=record.metadata.get("source_files", []),
                    relations=relations,
                    payload={**record.model_dump(mode="json"), "transaction_id": _normalize_transaction_id(record.flow_id or record.intent)},
                )
            )
        for document in documents:
            for item in _section_items(document.text, {"flows"}):
                values.append(
                    AssetCandidate(
                        asset_type="flow",
                        name=_flow_name_from_text(item),
                        description=item,
                        text=item,
                        tags=["utterance_flow"],
                        source_refs=[str(document.path)],
                        payload={
                            "utterances": [item],
                            "intent": _slug(item).replace("_", "."),
                            "transaction_id": _infer_transaction_id_from_text(item),
                        },
                    )
                )
        return values

    def _rule_candidates(self, documents: list[CorpusDocument], records: list[KnowledgeRecord]) -> list[AssetCandidate]:
        values: list[AssetCandidate] = []
        for document in documents:
            for item in _section_items(document.text, {"rules"}):
                values.append(
                    AssetCandidate(
                        asset_type="business_rule",
                        name=_rule_name_from_text(item),
                        description=_first_sentence(item),
                        text=item,
                        tags=["business_rule", *_matching_record_intents(item, records)],
                        source_refs=[str(document.path)],
                        relations=_record_relations_for_text(item, records),
                        payload={
                            "rule_text": item,
                            "source_section": "Rules",
                            **_extract_rule_structure(item),
                            "transaction_id": _record_transaction_id_for_text(item, records),
                        },
                    )
                )
            if not any(marker in document.path.name.lower() for marker in ["policy", "control", "memo"]):
                continue
            for title, body in _markdown_sections(document.text):
                title_lower = title.casefold()
                if not any(marker in title_lower for marker in ["control", "requirement", "threshold", "rule", "policy"]):
                    continue
                values.append(
                    AssetCandidate(
                        asset_type="business_rule",
                        name=title,
                        description=_first_sentence(body),
                        text=body,
                        tags=["business_rule", *_matching_record_intents(body, records)],
                        source_refs=[str(document.path)],
                        relations=_record_relations_for_text(body, records),
                        payload={
                            "source_section": title,
                            "rule_text": body,
                            **_extract_rule_structure(body),
                            "transaction_id": _record_transaction_id_for_text(body, records),
                            "ruleset_name": _ruleset_name_from_title(title),
                        },
                    )
                )
        return values

    def _process_candidates(self, documents: list[CorpusDocument], records: list[KnowledgeRecord]) -> list[AssetCandidate]:
        values: list[AssetCandidate] = []
        for document in documents:
            for item in _section_items(document.text, {"processes"}):
                values.append(
                    AssetCandidate(
                        asset_type="process",
                        name=_process_name_from_text(item),
                        description=_first_sentence(item),
                        text=item,
                        tags=["process_fragment", *_matching_record_intents(item, records)],
                        source_refs=[str(document.path)],
                        relations=_record_relations_for_text(item, records),
                        payload={
                            "steps_text": item,
                            "source_section": "Processes",
                            "transaction_id": _record_transaction_id_for_text(item, records) or _infer_transaction_id_from_text(item),
                        },
                    )
                )
            if document.path.name != "process_fragments.json":
                continue
            try:
                data = json.loads(document.text) or {}
            except json.JSONDecodeError:
                continue
            for fragment in data.get("fragments", []):
                title = str(fragment.get("title") or "").strip()
                text = str(fragment.get("text") or "").strip()
                if not title or not text:
                    continue
                values.append(
                    AssetCandidate(
                        asset_type="process",
                        name=title,
                        description=_first_sentence(text),
                        text=text,
                        tags=["process_fragment", *_matching_record_intents(text, records)],
                        source_refs=[str(document.path)],
                        relations=_record_relations_for_text(f"{title}\n{text}", records),
                        payload={
                            "source": data.get("source"),
                            "steps_text": text,
                            "transaction_id": _record_transaction_id_for_text(f"{title}\n{text}", records) or _infer_transaction_id_from_text(f"{title}\n{text}"),
                        },
                    )
                )
        return values

    def _plan_candidates(self, documents: list[CorpusDocument], records: list[KnowledgeRecord]) -> list[AssetCandidate]:
        values: list[AssetCandidate] = []
        for document in documents:
            for item in _section_items(document.text, {"plans"}):
                plan_name = _plan_name_from_text(item)
                values.append(
                    AssetCandidate(
                        asset_type="plan",
                        name=plan_name,
                        description=_first_sentence(item),
                        text=item,
                        tags=["orchestration_plan", *_matching_record_intents(item, records)],
                        source_refs=[str(document.path)],
                        relations=_record_relations_for_text(item, records),
                        payload={
                            "steps": [],
                            "plan_text": item,
                            "source_section": "Plans",
                            "transaction_id": _record_transaction_id_for_text(item, records) or _infer_transaction_id_from_text(item),
                        },
                    )
                )
            if "planning" not in document.path.name.lower():
                continue
            for title, body in _markdown_sections(document.text):
                if not title.casefold().startswith("plan:"):
                    continue
                plan_name = title.split(":", 1)[1].strip()
                step_names = _numbered_steps(body)
                relations = [
                    AssetRelation(type="has_step", target_asset_id=f"user_task.{_slug(step)}")
                    for step in step_names
                ]
                relations.extend(_record_relations_for_text(body, records))
                values.append(
                    AssetCandidate(
                        asset_type="plan",
                        name=plan_name,
                        description=_first_sentence(body),
                        text=body,
                        tags=["orchestration_plan", *_matching_record_intents(body, records)],
                        source_refs=[str(document.path)],
                        relations=relations,
                        payload={
                            "steps": step_names,
                            "plan_text": body,
                            "transaction_id": _record_transaction_id_for_text(body, records) or _infer_transaction_id_from_text(body),
                        },
                    )
                )
        return values

    def _qa_candidates(self, documents: list[CorpusDocument], records: list[KnowledgeRecord]) -> list[AssetCandidate]:
        values: list[AssetCandidate] = []
        for document in documents:
            for item in _section_items(document.text, {"qa"}):
                values.append(
                    AssetCandidate(
                        asset_type="qa",
                        name=item.rstrip("?") + "?",
                        description=item,
                        text=item,
                        tags=["qa", *_matching_record_intents(item, records)],
                        source_refs=[str(document.path)],
                        relations=_record_relations_for_text(item, records),
                        payload={
                            "question": item.rstrip("?") + "?",
                            "transaction_id": _record_transaction_id_for_text(item, records),
                        },
                    )
                )
            if not any(marker in document.path.name.lower() for marker in ["qa", "wiki", "support"]):
                continue
            sections = _markdown_sections(document.text)
            for title, body in sections:
                if title.casefold().startswith("q:") or title.casefold().startswith("question:"):
                    question = title.split(":", 1)[1].strip()
                    values.append(
                        AssetCandidate(
                            asset_type="qa",
                            name=question,
                            description=_first_sentence(body),
                            text=body,
                        tags=["qa", *_matching_record_intents(body, records)],
                        source_refs=[str(document.path)],
                        relations=_record_relations_for_text(body, records),
                        payload={
                            "question": question,
                            "answer": body,
                            "transaction_id": _record_transaction_id_for_text(body, records),
                        },
                    )
                )
        return values

    def _causality_candidates(self, documents: list[CorpusDocument], records: list[KnowledgeRecord]) -> list[AssetCandidate]:
        values: list[AssetCandidate] = []
        seen: set[str] = set()
        for document in documents:
            section_sentences = _section_items(document.text, {"causality"})
            if section_sentences:
                sentences = section_sentences
            else:
                if document.path.suffix.lower() in {".json", ".yaml", ".yml"}:
                    continue
                sentences = self.text_analyzer.sentences(document.text)
            for sentence in sentences:
                if _looks_like_structured_data(sentence):
                    continue
                hints = [hint for hint in self.relation_patterns.detect(sentence) if hint.family == "causality"]
                if not hints:
                    continue
                cause, effect = _split_cause_effect(sentence, hints[0].phrase)
                if not cause or not effect:
                    continue
                key = f"{_slug(cause)}::{hints[0].relation_type}::{_slug(effect)}"
                if key in seen:
                    continue
                seen.add(key)
                relations = _record_relations_for_text(sentence, records)
                values.append(
                    AssetCandidate(
                        asset_type="causality",
                        name=f"{cause} {hints[0].relation_type} {effect}",
                        description=sentence.strip(),
                        text=sentence.strip(),
                        tags=[hints[0].family, hints[0].relation_type],
                        source_refs=[str(document.path)],
                        relations=relations,
                        payload={
                            "cause_text": cause,
                            "effect_text": effect,
                            "relation_kind": hints[0].relation_type,
                            "sentence": sentence.strip(),
                            "transaction_id": _record_transaction_id_for_text(sentence, records),
                        },
                    )
                )
        return values

    def _enrich_causality_candidate(
        self,
        candidate: AssetCandidate,
        entity_map: dict[str, AssetCandidate],
        flow_ids: dict[str, KnowledgeRecord],
        reference_targets: list[AssetReferenceTarget],
    ) -> None:
        cause_text = str(candidate.payload.get("cause_text") or "")
        effect_text = str(candidate.payload.get("effect_text") or "")
        relation_kind = str(candidate.payload.get("relation_kind") or "causes")
        cause_target = self._target_for_text(cause_text, entity_map, flow_ids, reference_targets, relation_role="cause")
        effect_target = self._target_for_text(effect_text, entity_map, flow_ids, reference_targets, relation_role="effect")
        if self.relation_normalizer is not None:
            normalization = self.relation_normalizer.normalize_relation_type(
                relation_kind,
                source_asset_type="causality",
                target_asset_type="entity",
            )
            relation_kind = normalization.canonical_type
            candidate.payload["relation_kind_family"] = normalization.family
            candidate.payload["relation_kind_strategy"] = normalization.strategy
            candidate.payload["relation_kind_review_required"] = normalization.review_required
        if cause_target:
            candidate.relations.append(AssetRelation(type="has_cause", target_asset_id=cause_target))
        if effect_target:
            candidate.relations.append(AssetRelation(type="has_effect", target_asset_id=effect_target))
        if cause_target and effect_target:
            candidate.payload["canonical_name"] = f"{cause_target} {relation_kind} {effect_target}"
            candidate.name = f"{cause_target} {relation_kind} {effect_target}"
        candidate.payload["resolved_cause_asset_id"] = cause_target
        candidate.payload["resolved_effect_asset_id"] = effect_target

    def _target_for_text(
        self,
        text: str,
        entity_map: dict[str, AssetCandidate],
        flow_ids: dict[str, KnowledgeRecord],
        reference_targets: list[AssetReferenceTarget],
        *,
        relation_role: str,
    ) -> str | None:
        normalized = self._normalized_phrase(text)
        if not normalized:
            return None
        best_match: tuple[float, str] | None = None
        for target in reference_targets:
            score = self._reference_match_score(normalized, target, relation_role=relation_role)
            if score <= 0:
                continue
            if best_match is None or score > best_match[0]:
                best_match = (score, target.asset_id)
        if best_match is not None and best_match[0] >= 0.74:
            return best_match[1]
        normalized = _slug(text)
        if normalized in entity_map:
            return f"entity.{self.vocabulary.normalize_term(entity_map[normalized].name).canonical}"
        for key, record in flow_ids.items():
            if key == normalized or _slug(record.flow_name) == normalized:
                return f"flow.{record.flow_id}"
        return None

    def _build_reference_targets(self, candidates: list[AssetCandidate]) -> list[AssetReferenceTarget]:
        allowed = {"entity", "business_rule", "process", "flow", "plan", "user_task", "tool"}
        targets: list[AssetReferenceTarget] = []
        for candidate in candidates:
            if candidate.asset_type not in allowed:
                continue
            asset_id = self.canonicalizer._asset_id(candidate)
            terms = _dedupe_preserve(
                [
                    self._normalized_phrase(candidate.name),
                    *[self._normalized_phrase(alias) for alias in candidate.aliases],
                ]
            )
            filtered_terms = tuple(term for term in terms if term)
            if not filtered_terms:
                continue
            targets.append(
                AssetReferenceTarget(
                    asset_id=asset_id,
                    asset_type=candidate.asset_type,
                    name=candidate.name,
                    terms=filtered_terms,
                )
            )
        return targets

    def _reference_match_score(self, normalized_text: str, target: AssetReferenceTarget, *, relation_role: str) -> float:
        best = 0.0
        text_tokens = set(normalized_text.split())
        for term in target.terms:
            if normalized_text == term:
                best = max(best, 1.0)
                continue
            if normalized_text in term or term in normalized_text:
                best = max(best, 0.88)
            term_tokens = set(term.split())
            if text_tokens and term_tokens:
                overlap = len(text_tokens & term_tokens) / max(len(text_tokens), len(term_tokens))
                if overlap >= 0.5:
                    best = max(best, 0.55 + overlap * 0.3)
        if relation_role == "effect" and target.asset_type in {"flow", "process", "business_rule"}:
            best += 0.08
        if relation_role == "cause" and target.asset_type == "entity":
            best += 0.05
        return min(best, 1.0)

    def _is_entity_candidate(self, text: str, *, source: str) -> bool:
        normalized = self._normalized_phrase(text)
        if not normalized:
            return False
        reserved = {
            "process",
            "policy",
            "approval",
            "workflow",
            "rule",
            "plan",
            "proceso",
            "regla",
            "plan de accion",
            "document",
            "question",
            "task",
            "tool",
            "flow",
        }
        if normalized in reserved:
            return False
        if any(token in normalized.split() for token in GENERIC_ACTION_WORDS):
            return False
        if source != "section" and len(normalized.split()) > 4:
            return False
        if normalized.count(" ") > 4:
            return False
        return True

    @staticmethod
    def _normalized_phrase(value: str) -> str:
        return " ".join(str(value).casefold().replace("_", " ").replace(".", " ").split())

    def _entity_mentions_from_text(self, text: str) -> list[str]:
        phrases = self.text_analyzer.noun_phrases(text)
        values = [phrase for phrase in phrases if self._looks_like_business_phrase(phrase)]
        if values:
            return _dedupe_preserve(values)
        stripped = re.sub(r"^(el|la|los|las|un|una)\s+", "", text.strip(), flags=re.IGNORECASE)
        parts = re.split(
            r"\b(solicita|recibe|registra|valida|contiene|impacta|exige|respalda|soporta|aporta|incluye|actualiza|bloquea|habilita|impide)\b",
            stripped,
            flags=re.IGNORECASE,
            maxsplit=1,
        )
        fallback = parts[0].strip(" .,:;")
        return [fallback] if self._looks_like_business_phrase(fallback) else []

    @staticmethod
    def _looks_like_business_phrase(value: str) -> bool:
        normalized = " ".join(value.casefold().split())
        if not normalized or len(normalized.split()) > 4:
            return False
        tokens = normalized.split()
        if all(token in GENERIC_STOPWORDS for token in tokens):
            return False
        if any(token in GENERIC_ACTION_WORDS for token in tokens):
            return False
        return any(any(char.isalpha() for char in token) and token not in GENERIC_STOPWORDS for token in tokens)

    @staticmethod
    def _glossary_rows(documents: list[CorpusDocument]) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for document in documents:
            if document.path.suffix.lower() != ".csv":
                continue
            try:
                reader = csv.DictReader(document.text.splitlines())
                rows.extend({str(key): str(value) for key, value in row.items() if key} for row in reader)
            except Exception:
                continue
        return rows

    def _asset_system_prompt(self) -> str:
        return (
            "You extract reusable enterprise knowledge assets from unstructured corpus. "
            "Return only valid JSON. Do not assume banking or any industry. "
            "Infer assets only from the provided corpus. "
            "Entities are reusable business nouns or noun phrases. "
            "Business rules are constraints, policies, thresholds, or obligations. "
            "Processes are structured operational procedures. "
            "Plans are objective-oriented step sequences. "
            "QA items are user-facing questions and answers. "
            "Causalities express explicit cause/effect, prevent, or enable relations. "
            "Prefer generic enterprise interpretation over domain-specific assumptions."
        )

    def _normalize_relations(self, candidate: AssetCandidate) -> list[AssetRelation]:
        if self.relation_normalizer is None:
            return candidate.relations
        normalized_relations: list[AssetRelation] = []
        for relation in candidate.relations:
            target_asset_type = _asset_type_from_asset_id(relation.target_asset_id)
            normalized_relations.append(
                self.relation_normalizer.normalize_relation(
                    relation,
                    source_asset_type=candidate.asset_type,
                    target_asset_type=target_asset_type,
                )
            )
        return normalized_relations

    def _asset_user_content(self, documents: list[CorpusDocument]) -> list[dict[str, Any]]:
        content: list[dict[str, Any]] = [{"type": "text", "text": self._asset_schema_prompt()}]
        for doc in documents:
            if doc.kind == "image" and doc.data_url:
                content.append({"type": "text", "text": f"--- SOURCE IMAGE: {doc.path} ---"})
                content.append({"type": "image_url", "image_url": {"url": doc.data_url, "detail": "auto"}})
            else:
                content.append({"type": "text", "text": f"--- SOURCE: {doc.path} ---\n{doc.text[:12000]}"})
        return content

    def _asset_schema_prompt(self) -> str:
        return (
            "Produce this exact JSON object:\n"
            "{\n"
            '  "entities": [\n'
            '    {"name": "Entity name", "description": "Meaning", "aliases": ["alt name"], "evidence": ["supporting text"]}\n'
            "  ],\n"
            '  "business_rules": [\n'
            '    {"name": "Rule name", "description": "Rule meaning", "transaction_id": "transaction_key", "ruleset_name": "Ruleset display name", "rule_text": "Original rule wording", "conditions": ["condition text"], "consequences": ["consequence text"]}\n'
            "  ],\n"
            '  "processes": [\n'
            '    {"name": "Process name", "description": "What it does", "transaction_id": "transaction_key", "steps": ["step one", "step two"]}\n'
            "  ],\n"
            '  "plans": [\n'
            '    {"name": "Plan name", "objective": "Goal", "description": "Plan meaning", "transaction_id": "transaction_key", "steps": ["step one", "step two"]}\n'
            "  ],\n"
            '  "qas": [\n'
            '    {"question": "User question?", "answer": "Grounded answer", "transaction_id": "transaction_key"}\n'
            "  ],\n"
            '  "causalities": [\n'
            '    {"statement": "Original cause/effect statement", "transaction_id": "transaction_key", "relation_kind": "causes|prevents|enables|results_in|increases_risk_of|reduces_risk_of", "cause_text": "Cause phrase", "effect_text": "Effect phrase"}\n'
            "  ]\n"
            "}\n"
            "Rules:\n"
            "- Do not invent assets unsupported by the corpus.\n"
            "- Keep names reusable, concise, and neutral.\n"
            "- Prefer canonical names over full sentence fragments.\n"
            "- Only extract causalities when the corpus explicitly states cause/effect.\n"
            "- For business rules, extract the condition and the consequence separately whenever the corpus makes them explicit.\n"
            "- Use transaction_id for the business operation or request being served, such as opening an account, refinancing a loan, filing a claim, or updating a beneficiary.\n"
            "- If no assets of one family are present, return an empty array for that family.\n"
        )

    def _group_transaction_assets(self, candidates: list[AssetCandidate]) -> list[AssetCandidate]:
        asset_id_map = {self.canonicalizer._asset_id(candidate): candidate for candidate in candidates}
        transaction_groups: dict[str, list[AssetCandidate]] = {}
        for candidate in candidates:
            transaction_id = self._transaction_id_for_candidate(candidate)
            if not transaction_id:
                continue
            candidate.payload["transaction_id"] = transaction_id
            transaction_groups.setdefault(transaction_id, []).append(candidate)

        if not transaction_groups:
            return candidates

        ruleset_candidates = self._ruleset_candidates(transaction_groups)
        ruleset_id_map = {self.canonicalizer._asset_id(candidate): candidate for candidate in ruleset_candidates}
        asset_id_map.update(ruleset_id_map)

        asset_set_candidates = self._asset_set_candidates(transaction_groups, asset_id_map, ruleset_candidates)
        for candidate in [*ruleset_candidates, *asset_set_candidates]:
            candidate.relations = _dedupe_relations(self._normalize_relations(candidate))
        return [*candidates, *ruleset_candidates, *asset_set_candidates]

    def _ruleset_candidates(self, transaction_groups: dict[str, list[AssetCandidate]]) -> list[AssetCandidate]:
        candidates: list[AssetCandidate] = []
        for transaction_id, members in transaction_groups.items():
            rules = [member for member in members if member.asset_type == "business_rule"]
            if not rules:
                continue
            grouped_by_ruleset: dict[str, list[AssetCandidate]] = {}
            for rule in rules:
                ruleset_name = str(rule.payload.get("ruleset_name") or "").strip() or f"{_display_name_from_transaction_id(transaction_id)} Ruleset"
                grouped_by_ruleset.setdefault(ruleset_name, []).append(rule)
            for ruleset_name, grouped_rules in grouped_by_ruleset.items():
                relations: list[AssetRelation] = [
                    AssetRelation(type="groups_rule", target_asset_id=self.canonicalizer._asset_id(rule))
                    for rule in grouped_rules
                ]
                grouped_conditions: list[str] = []
                grouped_consequences: list[str] = []
                for rule in grouped_rules:
                    grouped_conditions.extend(str(value) for value in rule.payload.get("conditions", []) if str(value).strip())
                    grouped_consequences.extend(str(value) for value in rule.payload.get("consequences", []) if str(value).strip())
                    for relation in rule.relations:
                        if relation.type in {"uses_entity", "applies_to_flow", "applies_to_process", "applies_to_plan"}:
                            relations.append(relation)
                candidates.append(
                    AssetCandidate(
                        asset_type="ruleset",
                        name=ruleset_name,
                        description=f"Ruleset for transaction {transaction_id} with {len(grouped_rules)} business rules.",
                        text="\n".join(rule.text for rule in grouped_rules if rule.text),
                        tags=["ruleset", transaction_id],
                        source_refs=_dedupe_preserve([source for rule in grouped_rules for source in rule.source_refs]),
                        relations=_dedupe_relations(relations),
                        payload={
                            "transaction_id": transaction_id,
                            "ruleset_name": ruleset_name,
                            "rule_ids": [self.canonicalizer._asset_id(rule) for rule in grouped_rules],
                            "conditions": _dedupe_preserve(grouped_conditions),
                            "consequences": _dedupe_preserve(grouped_consequences),
                        },
                    )
                )
        return candidates

    def _asset_set_candidates(
        self,
        transaction_groups: dict[str, list[AssetCandidate]],
        asset_id_map: dict[str, AssetCandidate],
        ruleset_candidates: list[AssetCandidate],
    ) -> list[AssetCandidate]:
        rulesets_by_transaction: dict[str, list[AssetCandidate]] = {}
        for candidate in ruleset_candidates:
            transaction_id = str(candidate.payload.get("transaction_id") or "").strip()
            if transaction_id:
                rulesets_by_transaction.setdefault(transaction_id, []).append(candidate)

        values: list[AssetCandidate] = []
        for transaction_id, members in transaction_groups.items():
            member_ids = {self.canonicalizer._asset_id(candidate) for candidate in members}
            for ruleset in rulesets_by_transaction.get(transaction_id, []):
                member_ids.add(self.canonicalizer._asset_id(ruleset))
            pending = list(member_ids)
            while pending:
                current_asset_id = pending.pop()
                candidate = asset_id_map.get(current_asset_id)
                if candidate is None:
                    continue
                for relation in candidate.relations:
                    target = relation.target_asset_id
                    target_candidate = asset_id_map.get(target)
                    if target_candidate is None:
                        continue
                    if target not in member_ids:
                        member_ids.add(target)
                        pending.append(target)
            relations = [
                AssetRelation(
                    type=_group_relation_type_for(asset_id_map[member_id].asset_type),
                    target_asset_id=member_id,
                )
                for member_id in sorted(member_ids)
                if member_id in asset_id_map and asset_id_map[member_id].asset_type not in {"document", "asset_set"}
            ]
            grouped_assets = [asset_id_map[member_id] for member_id in sorted(member_ids) if member_id in asset_id_map]
            values.append(
                AssetCandidate(
                    asset_type="asset_set",
                    name=f"{_display_name_from_transaction_id(transaction_id)} Asset Set",
                    description=f"Transaction-scoped bundle for {transaction_id}.",
                    text="\n".join(asset.name or asset.asset_id for asset in grouped_assets),
                    tags=["asset_set", transaction_id],
                    source_refs=_dedupe_preserve([source for asset in grouped_assets for source in asset.source_refs]),
                    relations=_dedupe_relations(relations),
                    payload={
                        "transaction_id": transaction_id,
                        "asset_ids": sorted(member_ids),
                        "asset_types": sorted({asset.asset_type for asset in grouped_assets}),
                    },
                )
            )
        return values

    def _transaction_id_for_candidate(self, candidate: AssetCandidate) -> str:
        explicit = _normalize_transaction_id(candidate.payload.get("transaction_id"))
        if explicit:
            return explicit
        if candidate.asset_type == "flow":
            payload = candidate.payload if isinstance(candidate.payload, dict) else {}
            return _normalize_transaction_id(payload.get("flow_id") or payload.get("intent") or candidate.name)
        if candidate.asset_type == "business_rule":
            for relation in candidate.relations:
                if relation.type == "applies_to_flow":
                    return _normalize_transaction_id(relation.target_asset_id.split(".", 1)[1])
            return _normalize_transaction_id(candidate.payload.get("ruleset_name") or candidate.name)
        if candidate.asset_type in {"process", "plan", "qa", "causality"}:
            return _normalize_transaction_id(candidate.name)
        return ""


def _record_relations_for_text(text: str, records: list[KnowledgeRecord]) -> list[AssetRelation]:
    lowered = text.casefold()
    relations: list[AssetRelation] = []
    for record in records:
        if record.flow_name.casefold() in lowered or record.intent.casefold().replace(".", " ") in lowered:
            relations.append(AssetRelation(type="applies_to_flow", target_asset_id=f"flow.{record.flow_id}"))
        for task in record.user_tasks:
            task_key = str(task.user_task_id or task.task)
            if _slug(task_key) and _slug(task_key) in _slug(lowered):
                relations.append(AssetRelation(type="decomposes_to_user_task", target_asset_id=f"user_task.{task_key}"))
        for concept in record.concepts:
            normalized = _slug(concept).replace("_", " ")
            if concept.casefold() in lowered or normalized in lowered:
                relations.append(AssetRelation(type="uses_entity", target_asset_id=f"entity.{_slug(concept)}"))
    return _dedupe_relations(relations)


def _split_cause_effect(sentence: str, phrase: str) -> tuple[str, str]:
    parts = re.split(re.escape(phrase), sentence, flags=re.IGNORECASE, maxsplit=1)
    if len(parts) != 2:
        return "", ""
    cause = parts[0].strip(" .,:;-\n\t")
    effect = parts[1].strip(" .,:;-\n\t")
    return cause, effect


def _looks_like_structured_data(text: str) -> bool:
    compact = text.strip()
    if not compact:
        return True
    if compact.startswith(("{", "[", "\"")):
        return True
    if compact.count(":") >= 2 and any(char in compact for char in ['"', "{", "}", "[", "]"]):
        return True
    return False


def _asset_type_from_asset_id(asset_id: str) -> str | None:
    if "." not in str(asset_id):
        return None
    return str(asset_id).split(".", 1)[0]


def _markdown_sections(text: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    current_title: str | None = None
    current_lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            if current_title and current_lines:
                sections.append((current_title, "\n".join(current_lines).strip()))
            current_title = line.removeprefix("## ").strip()
            current_lines = []
            continue
        if current_title:
            current_lines.append(line)
    if current_title and current_lines:
        sections.append((current_title, "\n".join(current_lines).strip()))
    return sections


def _section_items(text: str, titles: set[str]) -> list[str]:
    values: list[str] = []
    for title, body in _markdown_sections(text):
        normalized_title = title.strip().casefold().rstrip(":")
        if normalized_title not in titles:
            continue
        for line in body.splitlines():
            match = re.match(r"\s*\d+\.\s+(.+)", line)
            if match:
                values.append(match.group(1).strip())
    return values


def _numbered_steps(text: str) -> list[str]:
    values: list[str] = []
    for line in text.splitlines():
        match = re.match(r"\s*\d+\.\s+(.+)", line)
        if match:
            values.append(match.group(1).strip().rstrip("."))
    return values


def _first_sentence(text: str) -> str:
    compact = " ".join(text.split())
    parts = re.split(r"(?<=[.!?])\s+", compact, maxsplit=1)
    return parts[0] if parts else compact[:160]


def _rule_name_from_text(text: str) -> str:
    compact = _first_sentence(text)
    compact = re.sub(r"^(si|toda|todo|el|la)\s+", "", compact, flags=re.IGNORECASE)
    return compact[:90].rstrip(".")


def _process_name_from_text(text: str) -> str:
    match = re.match(r"(?:El\s+)?proceso\s+de\s+(.+?)(?:\s+identifica|\s+recoge|\s+valida|\s+y\s+|\.)", text, flags=re.IGNORECASE)
    if match:
        return f"Process {match.group(1).strip()}"
    return _first_sentence(text)[:90].rstrip(".")


def _plan_name_from_text(text: str) -> str:
    match = re.match(r"Plan\s+para\s+(.+?)(?::|\.)", text, flags=re.IGNORECASE)
    if match:
        return f"Plan {match.group(1).strip()}"
    return _first_sentence(text)[:90].rstrip(".")


def _flow_name_from_text(text: str) -> str:
    compact = _first_sentence(text)
    compact = re.sub(r"^(el cliente (dice|pregunta|expresa|comenta|pide|solicita):?\s*)", "", compact, flags=re.IGNORECASE)
    return compact[:90].rstrip(".")


def _task_name_from_text(text: str) -> str:
    compact = _first_sentence(text)
    return compact[:90].rstrip(".")


def _tool_name_from_text(text: str) -> str:
    compact = _first_sentence(text)
    match = re.search(r"\b([a-z0-9]+\.[a-z0-9_.]+)\b", compact, flags=re.IGNORECASE)
    if match:
        return match.group(1)
    return compact[:90].rstrip(".")


def _matching_record_intents(text: str, records: list[KnowledgeRecord]) -> list[str]:
    lowered = text.casefold()
    values = []
    for record in records:
        needles = [record.flow_name, record.intent, *record.concepts]
        if any(str(needle).casefold() in lowered for needle in needles if needle):
            values.append(record.intent)
    return sorted(set(values))


def _record_transaction_id_for_text(text: str, records: list[KnowledgeRecord]) -> str:
    lowered = text.casefold()
    for record in records:
        needles = [record.flow_name, record.intent, *record.utterances]
        if any(str(needle).casefold() in lowered for needle in needles if needle):
            return _normalize_transaction_id(record.flow_id or record.intent)
    return ""


def _infer_transaction_id_from_text(text: str) -> str:
    normalized = " " + _normalize_free_text_local(text) + " "
    patterns = [
        ("customer.create", ("crear cliente", "crear un cliente", "create customer", "alta de cliente", "nuevo cliente")),
        ("loan.create", ("crear prestamo", "crear un prestamo", "create loan", "originacion de prestamo", "solicitud de prestamo")),
        ("loan.disbursement", ("desembolso del prestamo", "realizar el desembolso", "disbursement", "acredita fondos")),
        ("loan.payment", ("pagar mi prestamo", "pago de prestamo", "pay loan", "abono al prestamo")),
        ("loan.transfer_to_loan", ("transferir dinero a mi prestamo", "transferencia a prestamo", "transferir al prestamo", "transfer to loan")),
        ("loan.refinance", ("refinanc",)),
        ("savings_account.open", ("abrir una cuenta de ahorro", "open savings account")),
        ("money.transfer", ("transferir dinero a otra cuenta", "transfer money", "transferencia bancaria")),
        ("account.reactivate", ("activar una cuenta", "reactivar cuenta")),
        ("autopay.cancel", ("cancelar el pago automatico", "cancel automatic payment")),
        ("customer.update_profile", ("actualizar mis datos", "update personal data")),
        ("dispute.charge_report", ("cargo no reconocido", "reportar un cargo")),
        ("loan_application.status_review", ("revisar el estado de mi solicitud", "status of my application")),
        ("customer_onboarding.documents", ("documentos para onboarding", "documents for onboarding")),
        ("debt.restructure", ("reestructurar una deuda", "restructure debt")),
        ("transfer.limit_inquiry", ("limite de transferencia", "transfer limit")),
    ]
    for canonical, needles in patterns:
        if any(needle in normalized for needle in needles):
            return canonical
    return _normalize_transaction_id(text)


def _ruleset_name_from_title(title: str) -> str:
    compact = " ".join(str(title).replace(":", " ").split())
    if compact.casefold().endswith("ruleset"):
        return compact
    return f"{compact} Ruleset"


def _extract_rule_structure(text: str) -> dict[str, list[str]]:
    compact = " ".join(str(text).split())
    patterns = [
        r"(?i)\bif\b\s+(?P<condition>.+?)\s+\bthen\b\s+(?P<consequence>.+)",
        r"(?i)\bwhen\b\s+(?P<condition>.+?)\s+\bthen\b\s+(?P<consequence>.+)",
        r"(?i)\bsi\b\s+(?P<condition>.+?)\s+\bentonces\b\s+(?P<consequence>.+)",
        r"(?i)\bcuando\b\s+(?P<condition>.+?)\s+\bentonces\b\s+(?P<consequence>.+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, compact)
        if match:
            return {
                "conditions": [match.group("condition").strip(" .,:;")],
                "consequences": [match.group("consequence").strip(" .,:;")],
            }
    consequence_markers = [
        " must ",
        " debe ",
        " should ",
        " requiere ",
        " requires ",
        " blocks ",
        " bloquea ",
        " prevents ",
        " impide ",
    ]
    lowered = f" {compact.casefold()} "
    for marker in consequence_markers:
        if marker in lowered:
            before, after = compact.split(marker.strip(), 1) if marker.strip() in compact else (compact, "")
            if before.strip() and after.strip():
                return {
                    "conditions": [before.strip(" .,:;")],
                    "consequences": [after.strip(" .,:;")],
                }
    return {"conditions": [], "consequences": [compact] if compact else []}


def _normalize_transaction_id(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    normalized = _normalize_free_text_local(text).replace(" ", ".")
    normalized = re.sub(r"[^a-z0-9.]+", ".", normalized)
    normalized = re.sub(r"\.+", ".", normalized).strip(".")
    return normalized


def _normalize_free_text_local(value: str) -> str:
    value = value.casefold()
    replacements = str.maketrans(
        {
            "á": "a",
            "é": "e",
            "í": "i",
            "ó": "o",
            "ú": "u",
            "ñ": "n",
        }
    )
    value = value.translate(replacements)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def _display_name_from_transaction_id(transaction_id: str) -> str:
    return " ".join(part.capitalize() for part in transaction_id.split("_") if part) or "Transaction"


def _group_relation_type_for(asset_type: str) -> str:
    mapping = {
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
    return mapping.get(asset_type, "groups_entity")


def _slug(value: Any) -> str:
    text = str(value).strip().casefold()
    text = re.sub(r"[^a-z0-9_]+", "_", text)
    return re.sub(r"_+", "_", text).strip("_")


def _dedupe_preserve(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        candidate = str(value).strip()
        if not candidate:
            continue
        normalized = candidate.casefold()
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(candidate)
    return deduped


def _dedupe_relations(relations: list[AssetRelation]) -> list[AssetRelation]:
    seen: set[tuple[str, str]] = set()
    values: list[AssetRelation] = []
    for relation in relations:
        key = (relation.type, relation.target_asset_id)
        if key in seen:
            continue
        seen.add(key)
        values.append(relation)
    return values
