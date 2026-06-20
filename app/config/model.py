from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from app.config.settings import load_settings


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Model configuration file not found: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_extraction_schema() -> dict[str, Any]:
    return _load_yaml(load_settings().model_schema_path)


def load_asset_contracts() -> dict[str, dict[str, Any]]:
    contracts = load_extraction_schema().get("asset_contracts", {})
    return {
        str(name): config
        for name, config in contracts.items()
        if isinstance(config, dict)
    }


def load_asset_payload_composition() -> dict[str, list[str]]:
    return {
        asset_type: [str(field) for field in config.get("payload_fields", [])]
        for asset_type, config in load_asset_contracts().items()
    }


def load_node_type_model() -> dict[str, Any]:
    return _load_yaml(load_settings().node_type_model_path)


def load_node_policy() -> dict[str, set[str]]:
    raw = load_node_type_model().get("definition_types", {})
    return {
        definition_type: set(config.get("allowed_types", []))
        for definition_type, config in raw.items()
        if isinstance(config, dict)
    }


def _json_example(value: Any, indent: int = 2) -> str:
    formatted = json.dumps(value, indent=indent, ensure_ascii=False)
    return formatted


def _render_rules(rules: list[str]) -> list[str]:
    lines = ["Rules:"]
    for rule in rules:
        lines.append(f"- {rule}")
    return lines


def _render_contract(name: str, config: dict[str, Any]) -> list[str]:
    lines = [f"- {name}:"]
    if config.get("description"):
        lines.append(f"  description: {config['description']}")
    if config.get("lifecycle_states"):
        lines.append(f"  lifecycle_states: {', '.join(config['lifecycle_states'])}")
    if config.get("extraction_array"):
        lines.append(f"  output_array: {config['extraction_array']}")
    if config.get("required_fields"):
        lines.append(f"  required_fields: {', '.join(config['required_fields'])}")
    if config.get("optional_fields"):
        lines.append(f"  optional_fields: {', '.join(config['optional_fields'])}")
    if config.get("payload_fields"):
        lines.append(f"  payload_fields: {', '.join(config['payload_fields'])}")

    composition = config.get("composition")
    if composition:
        lines.append("  composition:")
        for line in _json_example(composition, indent=4).splitlines():
            lines.append(f"    {line}")

    relations = config.get("relations") or {}
    derived_relations = relations.get("derived_relations") if isinstance(relations, dict) else None
    if derived_relations:
        lines.append("  derived_relations:")
        for line in _json_example(derived_relations, indent=4).splitlines():
            lines.append(f"    {line}")
    allowed_relations = relations.get("allowed") if isinstance(relations, dict) else None
    if allowed_relations:
        lines.append(f"  allowed_relations: {', '.join(allowed_relations)}")

    runtime_semantics = config.get("runtime_semantics")
    if runtime_semantics:
        lines.append("  runtime_semantics:")
        for line in _json_example(runtime_semantics, indent=4).splitlines():
            lines.append(f"    {line}")
    return lines


def _render_type_definitions(schema: dict[str, Any]) -> list[str]:
    definitions = schema.get("type_definitions", {})
    if not definitions:
        return []
    lines = ["Type definitions:"]
    for name, config in definitions.items():
        if not isinstance(config, dict):
            continue
        lines.append(f"- {name}: {config.get('description', '')}".rstrip())
        if config.get("lifecycle_states"):
            lines.append(f"  lifecycle_states: {', '.join(config['lifecycle_states'])}")
        variants = config.get("variants") or {}
        for variant_name, variant in variants.items():
            if not isinstance(variant, dict):
                continue
            lines.append(f"  - {variant_name}: {variant.get('description', '')}".rstrip())
            if variant.get("required_fields"):
                lines.append(f"    required_fields: {', '.join(variant['required_fields'])}")
            if variant.get("optional_fields"):
                lines.append(f"    optional_fields: {', '.join(variant['optional_fields'])}")
    return lines


def _render_output_contract(schema: dict[str, Any], array_names: list[str]) -> list[str]:
    lines = ["Return this JSON object shape, with arrays populated from corpus evidence only:", "{"]
    for index, array_name in enumerate(array_names):
        suffix = "," if index < len(array_names) - 1 else ""
        lines.append(f'  "{array_name}": []{suffix}')
    lines.append("}")
    output_contract = schema.get("output_contract") or {}
    notes = output_contract.get("compatibility_notes") or []
    if notes:
        lines.append("")
        lines.append("Compatibility notes:")
        for note in notes:
            lines.append(f"- {note}")
    return lines


def flow_extraction_prompt() -> str:
    schema = load_extraction_schema()
    contracts = load_asset_contracts()
    output_contract = schema.get("output_contract") or {}
    array_names = [
        *output_contract.get("required_top_level_arrays", []),
        *output_contract.get("optional_top_level_arrays", []),
    ]
    lines: list[str] = ["Analyze this corpus and extract governed assets."]
    lines.extend(_render_output_contract(schema, array_names))
    lines.append("")
    lines.extend(_render_type_definitions(schema))
    lines.append("")
    lines.append("Asset contracts:")
    for name, config in contracts.items():
        lines.extend(_render_contract(name, config))

    global_rules = schema.get("rules", [])
    if global_rules:
        lines.append("")
        lines.extend(_render_rules(global_rules))

    return "\n".join(lines)


def asset_extraction_prompt() -> str:
    schema = load_extraction_schema()
    contracts = load_asset_contracts()
    asset_contracts = {
        name: config
        for name, config in contracts.items()
        if name not in {"flow", "user_task"}
    }
    array_names = [
        str(config.get("extraction_array") or name)
        for name, config in asset_contracts.items()
    ]
    lines: list[str] = ["Extract governed asset candidates from this corpus."]
    lines.extend(_render_output_contract(schema, array_names))
    lines.append("")
    lines.append("Asset contracts:")
    for name, config in asset_contracts.items():
        lines.extend(_render_contract(name, config))

    global_rules = schema.get("rules", [])
    if global_rules:
        lines.append("")
        lines.extend(_render_rules(global_rules))

    return "\n".join(lines)
