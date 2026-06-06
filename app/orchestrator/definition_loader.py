from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from app.models import ProcessDefinition


@dataclass(frozen=True)
class YamlExecutableDefinitionLoader:
    """Load flow/process execution definitions from YAML files."""

    flow_directory: Path
    process_directory: Path

    def load_processes(self) -> list[ProcessDefinition]:
        return [self._to_process_definition(payload, source="process") for payload in self._yaml_payloads(self.process_directory)]

    def load_flows(self) -> dict[str, ProcessDefinition]:
        definitions: dict[str, ProcessDefinition] = {}
        for payload in self._yaml_payloads(self.flow_directory):
            flow_id = str(payload.get("flow_id") or "").strip()
            if not flow_id:
                continue
            definitions[flow_id] = self._to_process_definition(payload, source="flow")
        return definitions

    def _yaml_payloads(self, directory: Path) -> list[dict]:
        if not directory.exists() or not directory.is_dir():
            return []
        values: list[dict] = []
        for path in sorted(directory.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in {".yaml", ".yml"}:
                continue
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if isinstance(payload, dict):
                payload = dict(payload)
                payload.setdefault("metadata", {})
                if isinstance(payload["metadata"], dict):
                    payload["metadata"]["source_path"] = str(path)
                values.append(payload)
        return values

    def _to_process_definition(self, payload: dict, *, source: str) -> ProcessDefinition:
        if source == "process":
            return ProcessDefinition(**payload)

        # Flow execution YAML reuses the process runtime shape with flow-oriented ids.
        flow_id = str(payload.get("flow_id") or "").strip()
        flow_name = str(payload.get("flow_name") or flow_id or "flow")
        process_like = {
            "process_id": str(payload.get("process_id") or f"flow.{flow_id}"),
            "process_name": str(payload.get("process_name") or flow_name),
            "version": payload.get("version") or "1.0.0",
            "status": payload.get("status") or "draft",
            "domain": payload.get("domain") or "flow",
            "owner": payload.get("owner") or "Flow Runtime",
            "description": payload.get("description") or f"Executable flow definition for {flow_id}",
            "related_flow_ids": payload.get("related_flow_ids") or [flow_id],
            "triggers": payload.get("triggers") or [],
            "inputs": payload.get("inputs") or [],
            "outputs": payload.get("outputs") or [],
            "actors": payload.get("actors") or [],
            "systems": payload.get("systems") or [],
            "documents": payload.get("documents") or [],
            "rules": payload.get("rules") or [],
            "decisions": payload.get("decisions") or [],
            "exceptions": payload.get("exceptions") or [],
            "integrations": payload.get("integrations") or [],
            "activities": payload.get("activities") or [],
            "execution_nodes": payload.get("execution_nodes") or payload.get("user_flow") or [],
            "transitions": payload.get("transitions") or [],
            "timers": payload.get("timers") or [],
            "async_continuations": payload.get("async_continuations") or [],
            "event_listeners": payload.get("event_listeners") or [],
            "compensations": payload.get("compensations") or [],
            "subprocesses": payload.get("subprocesses") or [],
            "message_correlations": payload.get("message_correlations") or [],
            "jobs": payload.get("jobs") or [],
            "metadata": payload.get("metadata") or {},
        }
        return ProcessDefinition(**process_like)
