from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from app.knowledge_base.models import EnterpriseAsset


@dataclass(frozen=True)
class ExecutableDefinitionWriter:
    flow_directory: Path
    process_directory: Path

    def emit_from_extraction(
        self,
        *,
        extraction: dict[str, Any],
        assets: list[EnterpriseAsset],
    ) -> list[Path]:
        self.flow_directory.mkdir(parents=True, exist_ok=True)
        self.process_directory.mkdir(parents=True, exist_ok=True)

        user_tasks_by_id = {
            str(item.get("user_task_id") or "").strip(): item
            for item in extraction.get("user_tasks", [])
            if str(item.get("user_task_id") or "").strip()
        }
        flow_assets_by_transaction = {
            str(asset.payload.get("transaction_id") or "").strip(): asset
            for asset in assets
            if asset.asset_type == "flow" and str(asset.payload.get("transaction_id") or "").strip()
        }
        process_assets_by_transaction = {
            str(asset.payload.get("transaction_id") or "").strip(): asset
            for asset in assets
            if asset.asset_type == "process" and str(asset.payload.get("transaction_id") or "").strip()
        }

        written: list[Path] = []
        for flow in extraction.get("flows", []):
            flow_id = str(flow.get("flow_id") or "").strip()
            if not flow_id:
                continue
            flow_asset = flow_assets_by_transaction.get(flow_id)
            process_asset = process_assets_by_transaction.get(flow_id)
            flow_path = self.flow_directory / f"{flow_id.replace('.', '_')}.flow.yaml"
            process_path = self.process_directory / f"{flow_id.replace('.', '_')}.process.yaml"

            flow_payload = self._build_flow_definition(
                flow=flow,
                flow_asset=flow_asset,
                user_tasks_by_id=user_tasks_by_id,
                existing=self._read_existing_yaml(flow_path),
            )
            process_payload = self._build_process_definition(
                flow=flow,
                flow_asset=flow_asset,
                process_asset=process_asset,
                user_tasks_by_id=user_tasks_by_id,
                existing=self._read_existing_yaml(process_path),
            )

            self._write_yaml(flow_path, flow_payload)
            self._write_yaml(process_path, process_payload)
            written.extend([flow_path, process_path])
        return written

    def _build_flow_definition(
        self,
        *,
        flow: dict[str, Any],
        flow_asset: EnterpriseAsset | None,
        user_tasks_by_id: dict[str, dict[str, Any]],
        existing: dict[str, Any] | None,
    ) -> dict[str, Any]:
        flow_id = str(flow.get("flow_id") or "").strip()
        flow_name = str(flow.get("flow_name") or self._display_name(flow_id)).strip()
        utterances = [str(value).strip() for value in flow.get("utterances", []) if str(value).strip()]
        payload = {
            "flow_id": flow_id,
            "flow_name": existing.get("flow_name") if existing else flow_name,
            "version": existing.get("version", "1.0.0") if existing else "1.0.0",
            "status": existing.get("status", "approved") if existing else "approved",
            "domain": existing.get("domain", self._default_domain(flow_id)) if existing else self._default_domain(flow_id),
            "owner": existing.get("owner", "Generated Operations") if existing else "Generated Operations",
            "description": self._flow_description(existing, flow_asset, flow_name),
            "related_flow_ids": [flow_id],
            "triggers": utterances or [flow_name],
            "inputs": [str(value).strip() for value in flow.get("inputs", []) if str(value).strip()],
            "outputs": [str(value).strip() for value in flow.get("outputs", []) if str(value).strip()],
            "user_flow": self._user_flow_nodes(flow=flow, user_tasks_by_id=user_tasks_by_id),
        }
        return self._drop_empty(payload)

    def _build_process_definition(
        self,
        *,
        flow: dict[str, Any],
        flow_asset: EnterpriseAsset | None,
        process_asset: EnterpriseAsset | None,
        user_tasks_by_id: dict[str, dict[str, Any]],
        existing: dict[str, Any] | None,
    ) -> dict[str, Any]:
        flow_id = str(flow.get("flow_id") or "").strip()
        process_name = (
            existing.get("process_name")
            if existing
            else (
                (process_asset.name if process_asset else None)
                or f"{self._display_name(flow_id)} Process"
            )
        )
        process_payload = {
            "process_id": existing.get("process_id", flow_id) if existing else flow_id,
            "process_name": process_name,
            "version": existing.get("version", "1.0.0") if existing else "1.0.0",
            "status": existing.get("status", "approved") if existing else "approved",
            "domain": existing.get("domain", self._default_domain(flow_id)) if existing else self._default_domain(flow_id),
            "owner": existing.get("owner", "Generated Operations") if existing else "Generated Operations",
            "description": self._process_description(existing, process_asset, flow_asset, process_name),
            "related_flow_ids": [flow_id],
            "triggers": [str(value).strip() for value in flow.get("utterances", []) if str(value).strip()],
            "inputs": [str(value).strip() for value in flow.get("inputs", []) if str(value).strip()],
            "outputs": [str(value).strip() for value in flow.get("outputs", []) if str(value).strip()],
            "user_flow": self._user_flow_nodes(flow=flow, user_tasks_by_id=user_tasks_by_id),
        }
        return self._drop_empty(process_payload)

    def _user_flow_nodes(
        self,
        *,
        flow: dict[str, Any],
        user_tasks_by_id: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        nodes: list[dict[str, Any]] = [
            {
                "name": "start",
                "type": "start",
                "implementation": "builtin.start",
                "description": "Start flow execution.",
            }
        ]
        flow_inputs = [str(value).strip() for value in flow.get("inputs", []) if str(value).strip()]
        refs = [str(value).strip() for value in flow.get("user_task_refs", []) if str(value).strip()]
        for index, ref in enumerate(refs):
            user_task = user_tasks_by_id.get(ref) or {}
            nodes.append(
                self._user_task_node(
                    user_task_id=ref,
                    user_task=user_task,
                    required_inputs=flow_inputs if index == 0 else [],
                )
            )
        nodes.append(
            {
                "name": "end",
                "type": "end",
                "implementation": "builtin.end",
                "description": "Finish flow execution.",
            }
        )
        return nodes

    def _user_task_node(
        self,
        *,
        user_task_id: str,
        user_task: dict[str, Any],
        required_inputs: list[str],
    ) -> dict[str, Any]:
        description = str(user_task.get("description") or f"Execute {user_task_id}.").strip()
        node = {
            "name": user_task_id,
            "type": "user_task",
            "implementation": f"task.{user_task_id}",
            "description": description,
            "required_inputs": required_inputs,
            "user_actions": self._serialize_user_actions(user_task),
        }
        return self._drop_empty(node)

    def _serialize_user_actions(self, user_task: dict[str, Any]) -> list[dict[str, Any]]:
        values: list[dict[str, Any]] = []
        for raw_action in user_task.get("user_actions", []) or []:
            if not isinstance(raw_action, dict):
                continue
            action_name = str(raw_action.get("action_id") or raw_action.get("action") or "").strip()
            if not action_name:
                continue
            item = {
                "action": action_name,
                "type": str(raw_action.get("type") or "back").strip(),
                "implementation_type": str(raw_action.get("implementation_type") or "").strip() or None,
                "tool": str(raw_action.get("tool_id") or raw_action.get("tool") or "").strip() or None,
                "operation": raw_action.get("operation"),
                "resource": raw_action.get("resource"),
                "label": raw_action.get("label"),
                "triggers": raw_action.get("triggers"),
                "description": raw_action.get("description"),
            }
            if item["type"] == "front":
                item["tool"] = None
            values.append(self._drop_empty(item))
        return values

    @staticmethod
    def _read_existing_yaml(path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return loaded if isinstance(loaded, dict) else None

    @staticmethod
    def _write_yaml(path: Path, payload: dict[str, Any]) -> None:
        path.write_text(
            yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )

    @staticmethod
    def _default_domain(flow_id: str) -> str:
        parts = [part for part in flow_id.split(".") if part]
        if len(parts) <= 1:
            return parts[0] if parts else "generated"
        return ".".join(parts[:-1])

    @staticmethod
    def _display_name(identifier: str) -> str:
        return " ".join(part.capitalize() for part in identifier.replace("_", ".").split(".") if part)

    @staticmethod
    def _flow_description(existing: dict[str, Any] | None, flow_asset: EnterpriseAsset | None, flow_name: str) -> str:
        if existing and existing.get("description"):
            return str(existing["description"])
        if flow_asset and flow_asset.description:
            return flow_asset.description
        return f"Executable flow definition for {flow_name}."

    @staticmethod
    def _process_description(
        existing: dict[str, Any] | None,
        process_asset: EnterpriseAsset | None,
        flow_asset: EnterpriseAsset | None,
        process_name: str,
    ) -> str:
        if existing and existing.get("description"):
            return str(existing["description"])
        if process_asset and process_asset.description:
            return process_asset.description
        if flow_asset and flow_asset.description:
            return flow_asset.description
        return f"Executable process definition for {process_name}."

    @staticmethod
    def _drop_empty(value: dict[str, Any]) -> dict[str, Any]:
        return {
            key: item
            for key, item in value.items()
            if item not in (None, "", [], {})
        }
