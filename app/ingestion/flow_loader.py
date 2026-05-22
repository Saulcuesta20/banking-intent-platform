from __future__ import annotations

import json
from pathlib import Path

from app.capability.registry import RegistryCapabilityProvider
from app.ingestion.providers import KnowledgeIngestionProvider
from app.models import Action, KnowledgeRecord, Task, UserTask
from app.ontology.service import OntologyTermNormalizer


SUPPORTED_SUFFIXES = {
    ".json",
    ".md",
    ".markdown",
    ".html",
    ".htm",
    ".pdf",
    ".yaml",
    ".yml",
    ".bpmn",
}


class FlowKnowledgeLoader:
    def __init__(self, ontology_normalizer: OntologyTermNormalizer | None = None):
        self.ontology_normalizer = ontology_normalizer or OntologyTermNormalizer()

    def load_directory(self, directory: Path) -> list[KnowledgeRecord]:
        if not directory.exists():
            return []

        user_task_catalog = self._load_user_task_catalog(directory)
        records: list[KnowledgeRecord] = []
        for path in sorted(directory.rglob("*")):
            if path.is_file() and path.suffix.lower() == ".json" and ".user_task" not in path.name:
                maybe_record = self.load_file(path, user_task_catalog)
                if maybe_record is not None:
                    records.append(maybe_record)
        return records

    def load_file(
        self,
        path: Path,
        user_task_catalog: dict[str, UserTask] | None = None,
    ) -> KnowledgeRecord | None:
        data = json.loads(path.read_text(encoding="utf-8"))
        required_keys = {"intent", "business_event", "plan"}
        if not required_keys.issubset(data):
            return None

        user_tasks = self._load_user_tasks(data, user_task_catalog or self._load_user_task_catalog(path.parent))
        tasks = [user_task.to_task() for user_task in user_tasks]
        if not tasks:
            tasks = [Task(task=item["task"], type=item["type"]) for item in data.get("tasks", [])]

        ontology_nodes = list(data.get("ontology_nodes", []))
        ontology_aliases = dict(data.get("ontology_aliases", {}))
        if not ontology_aliases:
            ontology_aliases = self.ontology_normalizer.build_aliases_for_ontology_nodes(ontology_nodes)

        return KnowledgeRecord(
            flow_id=data.get("flow_id", data["intent"]),
            flow_name=data.get("flow_name", data["intent"].replace(".", " ").replace("_", " ").title()),
            intent=data["intent"],
            confidence=float(data.get("confidence", 0.75)),
            business_event=data["business_event"],
            utterances=list(data.get("utterances", [])),
            plan=list(data["plan"]),
            tasks=tasks,
            user_tasks=user_tasks,
            capabilities=list(data.get("capabilities", [])),
            ontology_nodes=ontology_nodes,
            ontology_aliases=ontology_aliases,
            explanation=data.get("explanation", "Matched from flow knowledge."),
            source=str(path),
            metadata=dict(data.get("metadata", {})),
        )

    def _load_user_task_catalog(self, directory: Path) -> dict[str, UserTask]:
        roots = [directory]
        if directory.name == "flows":
            roots.append(directory.parent / "user_tasks")
        catalog: dict[str, UserTask] = {}
        for root in roots:
            if not root.exists():
                continue
            for path in sorted(root.rglob("*.user_task.json")):
                data = json.loads(path.read_text(encoding="utf-8"))
                task = self._user_task_from_json(data)
                catalog[task.user_task_id or task.task] = task
                catalog[task.task] = task
        return catalog

    def _user_task_from_json(
        self,
        data: dict[str, object],
        sequence: int | None = None,
    ) -> UserTask:
        return UserTask(
            user_task_id=data.get("user_task_id"),
            task=str(data["task"]),
            type=str(data["type"]),
            sequence=sequence if sequence is not None else data.get("sequence"),
            name=data.get("name"),
            description=data.get("description"),
            front_actions=[
                Action(**action)
                for action in data.get("front_actions", [])
            ],
            back_actions=[
                Action(**action)
                for action in data.get("back_actions", [])
            ],
        )

    def _load_user_tasks(
        self,
        data: dict[str, object],
        user_task_catalog: dict[str, UserTask],
    ) -> list[UserTask]:
        refs = data.get("user_task_refs")
        if isinstance(refs, list):
            resolved = []
            for index, ref in enumerate(refs, start=1):
                if isinstance(ref, str):
                    ref_id = ref
                    sequence = index
                elif isinstance(ref, dict):
                    ref_id = str(ref.get("user_task_id") or ref.get("task"))
                    sequence = ref.get("sequence", index)
                else:
                    continue
                task = user_task_catalog.get(ref_id)
                if task is None:
                    continue
                resolved.append(task.model_copy(update={"sequence": sequence}))
            return resolved

        raw_user_tasks = data.get("user_tasks")
        if isinstance(raw_user_tasks, list):
            return [
                self._user_task_from_json(item, item.get("sequence"))
                for item in raw_user_tasks
                if isinstance(item, dict) and "task" in item and "type" in item
            ]

        return [
            UserTask(
                task=item["task"],
                type=item["type"],
                sequence=index,
                front_actions=[],
                back_actions=[],
            )
            for index, item in enumerate(data.get("tasks", []), start=1)
            if isinstance(item, dict) and "task" in item and "type" in item
        ]


class FileKnowledgeIngestionProvider(KnowledgeIngestionProvider):
    def __init__(self, flow_directory: Path, processed_directory: Path):
        self.flow_directory = flow_directory
        self.processed_directory = processed_directory
        self.loader = FlowKnowledgeLoader()

    def ingest(self, source: Path) -> list[KnowledgeRecord]:
        source_files = self._discover_source_files(source)
        records = self.loader.load_directory(self.flow_directory)
        action_registry = RegistryCapabilityProvider().build_action_registry(records)
        self.processed_directory.mkdir(parents=True, exist_ok=True)
        index_path = self.processed_directory / "knowledge_index.json"
        payload = {
            "source": str(source),
            "source_files": [str(path) for path in source_files],
            "action_registry": [entry.to_dict() for entry in action_registry],
            "records": [self._record_to_json(record) for record in records],
        }
        index_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return records

    def _discover_source_files(self, source: Path) -> list[Path]:
        if not source.exists():
            return []
        if source.is_file():
            return [source] if source.suffix.lower() in SUPPORTED_SUFFIXES else []
        return [
            path
            for path in sorted(source.rglob("*"))
            if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
        ]

    def _record_to_json(self, record: KnowledgeRecord) -> dict[str, object]:
        return {
            "intent": record.intent,
            "flow_id": record.flow_id,
            "flow_name": record.flow_name,
            "confidence": record.confidence,
            "business_event": record.business_event,
            "utterances": record.utterances,
            "plan": record.plan,
            "tasks": [task.to_dict() for task in record.tasks],
            "user_task_refs": [
                {"user_task_id": task.user_task_id or task.task, "sequence": task.sequence}
                for task in record.user_tasks
            ],
            "user_tasks": [task.to_dict() for task in record.user_tasks],
            "capabilities": record.capabilities,
            "ontology_nodes": record.ontology_nodes,
            "ontology_aliases": record.ontology_aliases,
            "explanation": record.explanation,
            "source": record.source,
            "metadata": record.metadata,
        }
