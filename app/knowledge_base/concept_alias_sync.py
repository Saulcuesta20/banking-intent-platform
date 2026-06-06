from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from app.knowledge_base.catalog_store import AssetCatalogStore
from app.knowledge_base.models import EnterpriseAsset
from app.knowledge_base.vocabulary import ConceptVocabulary
from app.knowledge_base.adapters.vector.qdrant import QdrantKnowledgeBaseVectorAdapter


@dataclass(frozen=True)
class ConceptAliasSyncResult:
    updated: bool
    added_aliases: int
    skipped_existing: int
    skipped_ambiguous: int
    skipped_low_score: int
    skipped_no_match: int
    concept_aliases_path: Path
    approved_aliases: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class ConceptAliasSyncService:
    concept_aliases_path: Path
    vector_adapter: QdrantKnowledgeBaseVectorAdapter | None = None
    vector_collection: str = "concept_alias_catalog"
    similarity_threshold: float = 0.84
    ambiguity_margin: float = 0.05
    max_alias_terms_per_asset: int = 8
    allowed_asset_types: tuple[str, ...] = ("entity", "business_rule", "tool", "plan", "qa")

    def sync_from_catalog(self, catalog: AssetCatalogStore) -> ConceptAliasSyncResult:
        vocabulary = ConceptVocabulary(synonym_catalog_path=self.concept_aliases_path)
        current_catalog = self._load_catalog()
        self._seed_vector_index(vocabulary, current_catalog)

        if self.vector_adapter is None:
            return ConceptAliasSyncResult(
                updated=False,
                added_aliases=0,
                skipped_existing=0,
                skipped_ambiguous=0,
                skipped_low_score=0,
                skipped_no_match=0,
                concept_aliases_path=self.concept_aliases_path,
            )

        assets = catalog.list_assets(status="approved", limit=10_000)
        candidate_aliases = self._collect_candidate_aliases(assets, vocabulary)

        added_aliases = 0
        skipped_existing = 0
        skipped_ambiguous = 0
        skipped_low_score = 0
        skipped_no_match = 0
        approved_aliases: dict[str, list[str]] = {}

        for alias, source_asset in candidate_aliases:
            target = self._resolve_candidate_alias(alias, vocabulary, current_catalog)
            if target is None:
                skipped_no_match += 1
                continue
            canonical, score, reason = target
            if score < self.similarity_threshold:
                skipped_low_score += 1
                continue
            if reason == "ambiguous":
                skipped_ambiguous += 1
                continue
            aliases = current_catalog.setdefault(canonical, [])
            if alias in aliases:
                skipped_existing += 1
                continue
            aliases.append(alias)
            approved_aliases.setdefault(canonical, []).append(alias)
            added_aliases += 1

        if added_aliases > 0:
            self._write_catalog(current_catalog)

        return ConceptAliasSyncResult(
            updated=added_aliases > 0,
            added_aliases=added_aliases,
            skipped_existing=skipped_existing,
            skipped_ambiguous=skipped_ambiguous,
            skipped_low_score=skipped_low_score,
            skipped_no_match=skipped_no_match,
            concept_aliases_path=self.concept_aliases_path,
            approved_aliases=approved_aliases,
        )

    def _collect_candidate_aliases(
        self,
        assets: list[dict[str, Any]],
        vocabulary: ConceptVocabulary,
    ) -> list[tuple[str, dict[str, Any]]]:
        candidates: list[tuple[str, dict[str, Any]]] = []
        seen: set[str] = set()
        for row in assets:
            asset_type = str(row.get("asset_type") or "")
            if asset_type not in self.allowed_asset_types:
                continue
            payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
            terms: list[str] = []
            name = str(row.get("name") or "").strip()
            if name:
                terms.append(name)
            canonical_name = str(payload.get("canonical_name") or "").strip()
            if canonical_name:
                terms.append(canonical_name)
            aliases = payload.get("aliases") if isinstance(payload.get("aliases"), list) else []
            for alias in aliases:
                if isinstance(alias, str) and alias.strip():
                    terms.append(alias.strip())
            for term in terms[: self.max_alias_terms_per_asset]:
                normalized = vocabulary.normalize_text(term)
                if not self._looks_like_alias_candidate(normalized):
                    continue
                if normalized in seen:
                    continue
                seen.add(normalized)
                candidates.append((normalized, row))
        return candidates

    def _resolve_candidate_alias(
        self,
        alias: str,
        vocabulary: ConceptVocabulary,
        current_catalog: dict[str, list[str]],
    ) -> tuple[str, float, str] | None:
        if self.vector_adapter is None:
            return None
        results = self.vector_adapter.search_texts(self.vector_collection, alias, limit=3)
        if not results:
            return None
        first = results[0]
        first_payload = first.get("payload") if isinstance(first.get("payload"), dict) else {}
        canonical = str(first_payload.get("canonical_concept") or "").strip()
        if not canonical:
            return None
        score = float(first.get("score") or 0.0)
        if len(results) > 1:
            second_score = float(results[1].get("score") or 0.0)
            if score - second_score < self.ambiguity_margin:
                return canonical, score, "ambiguous"
        if canonical not in current_catalog:
            return None
        return canonical, score, "approved"

    def _seed_vector_index(
        self,
        vocabulary: ConceptVocabulary,
        current_catalog: dict[str, list[str]],
    ) -> None:
        if self.vector_adapter is None:
            return
        records: list[dict[str, Any]] = []
        for canonical, aliases in current_catalog.items():
            normalized_canonical = vocabulary.normalize_text(canonical).replace(" ", "_")
            records.append(
                {
                    "id": f"concept::{normalized_canonical}::{normalized_canonical}",
                    "text": canonical,
                    "payload": {
                        "canonical_concept": normalized_canonical,
                        "alias": canonical,
                        "alias_kind": "canonical",
                    },
                }
            )
            for alias in aliases:
                normalized_alias = vocabulary.normalize_text(alias).replace(" ", "_")
                records.append(
                    {
                        "id": f"concept::{normalized_canonical}::{normalized_alias}",
                        "text": alias,
                        "payload": {
                            "canonical_concept": normalized_canonical,
                            "alias": alias,
                            "alias_kind": "synonym",
                        },
                    }
                )
        self.vector_adapter.upsert_texts(self.vector_collection, records)

    def _load_catalog(self) -> dict[str, list[str]]:
        if not self.concept_aliases_path.exists():
            return {}
        raw = yaml.safe_load(self.concept_aliases_path.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            return {}
        catalog: dict[str, list[str]] = {}
        for canonical, aliases in raw.items():
            if not isinstance(aliases, list):
                continue
            canonical_key = self._normalize_catalog_key(str(canonical))
            values: list[str] = []
            seen: set[str] = set()
            for alias in aliases:
                value = str(alias).strip()
                if not value:
                    continue
                normalized = value.casefold()
                if normalized in seen:
                    continue
                seen.add(normalized)
                values.append(value)
            catalog[canonical_key] = values
        return catalog

    def _write_catalog(self, catalog: dict[str, list[str]]) -> None:
        self.concept_aliases_path.parent.mkdir(parents=True, exist_ok=True)
        ordered_catalog = {key: sorted(values, key=lambda value: value.casefold()) for key, values in sorted(catalog.items())}
        self.concept_aliases_path.write_text(
            yaml.safe_dump(ordered_catalog, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )

    @staticmethod
    def _looks_like_alias_candidate(value: str) -> bool:
        text = " ".join(value.split())
        if not text or len(text) < 3:
            return False
        if len(text.split()) > 5:
            return False
        if any(char.isdigit() for char in text):
            return False
        if text in {"true", "false", "none", "null", "yes", "no"}:
            return False
        if "  " in text:
            return False
        return any(char.isalpha() for char in text)

    @staticmethod
    def _normalize_catalog_key(value: str) -> str:
        return ConceptVocabulary().normalize_text(value).replace(" ", "_")
