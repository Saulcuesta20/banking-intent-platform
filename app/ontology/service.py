from __future__ import annotations

import json
import os
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class NormalizedTerm:
    raw: str
    canonical: str
    aliases: list[str] = field(default_factory=list)


class OntologyTermNormalizer:
    """Normalize domain terms and provide ingestion-time synonym aliases."""

    def __init__(
        self,
        synonym_catalog: dict[str, list[str]] | None = None,
        synonym_catalog_path: Path | str | None = None,
    ):
        self.synonym_catalog = synonym_catalog if synonym_catalog is not None else self._load_synonym_catalog(
            synonym_catalog_path
        )
        self._alias_to_canonical = self._build_alias_index(self.synonym_catalog)

    def normalize_term(self, term: str) -> NormalizedTerm:
        normalized = self.normalize_text(term).replace(" ", "_")
        canonical = self._alias_to_canonical.get(normalized, normalized)
        aliases = self.aliases_for(canonical)
        return NormalizedTerm(raw=term, canonical=canonical, aliases=aliases)

    def normalize_terms(self, terms: list[str]) -> list[NormalizedTerm]:
        values: list[NormalizedTerm] = []
        seen: set[str] = set()
        for term in terms:
            normalized = self.normalize_term(term)
            if normalized.canonical in seen:
                continue
            values.append(normalized)
            seen.add(normalized.canonical)
        return values

    def aliases_for(self, canonical: str) -> list[str]:
        normalized = self.normalize_text(canonical).replace(" ", "_")
        aliases = [normalized, *self.synonym_catalog.get(normalized, [])]
        return self._dedupe([self.normalize_text(alias) for alias in aliases])

    def build_aliases_for_ontology_nodes(self, ontology_nodes: list[str]) -> dict[str, list[str]]:
        aliases_by_node: dict[str, list[str]] = {}
        for node in ontology_nodes:
            canonical = self._ontology_key(node)
            aliases = self.aliases_for(canonical)
            if aliases:
                aliases_by_node[node] = aliases
        return aliases_by_node

    def expand_search_terms(self, terms: list[str]) -> list[str]:
        expanded: list[str] = []
        seen: set[str] = set()
        for term in terms:
            normalized = self.normalize_text(term)
            self._append_unique(expanded, seen, normalized)
            normalized_term = self.normalize_term(normalized)
            self._append_unique(expanded, seen, normalized_term.canonical.replace("_", " "))
            self._append_unique(expanded, seen, normalized_term.canonical)
            for alias in normalized_term.aliases:
                self._append_unique(expanded, seen, alias)
        return expanded

    def normalize_text(self, value: str) -> str:
        without_accents = unicodedata.normalize("NFKD", str(value))
        ascii_value = without_accents.encode("ascii", "ignore").decode("ascii")
        text = ascii_value.lower().replace("_", " ")
        text = re.sub(r"[^a-z0-9 ]+", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    def _load_synonym_catalog(self, synonym_catalog_path: Path | str | None = None) -> dict[str, list[str]]:
        path = Path(
            synonym_catalog_path
            or os.getenv("ONTOLOGY_SYNONYM_CATALOG_PATH", "")
            or Path(__file__).resolve().parents[2] / "data" / "ontology" / "term_synonyms.json"
        )
        if not path.exists():
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"Ontology synonym catalog must be a JSON object: {path}")
        catalog: dict[str, list[str]] = {}
        for canonical, aliases in data.items():
            if not isinstance(aliases, list):
                continue
            catalog[str(canonical)] = [str(alias) for alias in aliases]
        return catalog

    def _ontology_key(self, value: str) -> str:
        text = re.sub(r"(?<!^)(?=[A-Z])", "_", str(value)).lower()
        text = self.normalize_text(text)
        return text.replace(" ", "_")

    def _build_alias_index(self, catalog: dict[str, list[str]]) -> dict[str, str]:
        index: dict[str, str] = {}
        for canonical, aliases in catalog.items():
            normalized_canonical = self.normalize_text(canonical).replace(" ", "_")
            index[normalized_canonical] = normalized_canonical
            for alias in aliases:
                normalized_alias = self.normalize_text(alias).replace(" ", "_")
                index[normalized_alias] = normalized_canonical
        return index

    def _dedupe(self, values: list[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for value in values:
            if not value or value in seen:
                continue
            deduped.append(value)
            seen.add(value)
        return deduped

    def _append_unique(self, values: list[str], seen: set[str], value: str) -> None:
        if value and value not in seen:
            values.append(value)
            seen.add(value)
