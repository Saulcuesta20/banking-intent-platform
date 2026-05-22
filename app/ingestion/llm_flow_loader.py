from __future__ import annotations

import json
import base64
import mimetypes
import os
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from app.ingestion.reasoning import IngestionReasoningService
from app.models import Action, UserTask
from app.ontology.service import OntologyTermNormalizer


SUPPORTED_CORPUS_SUFFIXES = {
    ".csv",
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".bmp",
    ".tif",
    ".tiff",
    ".docx",
    ".txt",
    ".md",
    ".markdown",
    ".json",
    ".yaml",
    ".yml",
    ".bpmn",
}

TEXT_CORPUS_SUFFIXES = SUPPORTED_CORPUS_SUFFIXES - {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".bmp",
    ".tif",
    ".tiff",
    ".docx",
}

IMAGE_CORPUS_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".bmp",
    ".tif",
    ".tiff",
}

TECHNICAL_OPERATION_SUFFIXES = {
    "read",
    "create",
    "update",
    "delete",
    "calculate",
    "validate",
    "post",
    "get",
    "send",
    "sync",
    "notify",
    "match",
    "normalize",
}


class FlowExtractionError(RuntimeError):
    pass


class LLMClient(Protocol):
    def complete_json(self, system_prompt: str, user_content: str | list[dict[str, Any]]) -> dict[str, Any]:
        pass


@dataclass(frozen=True)
class CorpusDocument:
    path: Path
    text: str = ""
    kind: str = "text"
    data_url: str | None = None


class OpenAICompatibleLLMClient:
    """Small OpenAI-compatible chat completions client using only stdlib."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout_seconds: int = 90,
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("FLOW_EXTRACTOR_MODEL", "gpt-4o-mini")
        self.base_url = (base_url or os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        self.timeout_seconds = timeout_seconds
        if not self.api_key:
            raise FlowExtractionError("OPENAI_API_KEY is required for LLM flow extraction.")

    def complete_json(self, system_prompt: str, user_content: str | list[dict[str, Any]]) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
        }
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise FlowExtractionError(f"LLM request failed: {exc.code} {detail}") from exc
        except urllib.error.URLError as exc:
            raise FlowExtractionError(f"LLM request failed: {exc.reason}") from exc

        data = json.loads(raw)
        content = data["choices"][0]["message"]["content"]
        return json.loads(content)


class CorpusFlowLoader:
    def __init__(
        self,
        llm_client: LLMClient,
        max_pdf_image_pages: int = 3,
        reasoning_service: IngestionReasoningService | None = None,
        ontology_normalizer: OntologyTermNormalizer | None = None,
    ):
        self.llm_client = llm_client
        self.max_pdf_image_pages = max_pdf_image_pages
        self.reasoning_service = reasoning_service
        self.ontology_normalizer = ontology_normalizer or OntologyTermNormalizer()

    def extract(self, raw_directory: Path) -> dict[str, Any]:
        documents = self.load_corpus(raw_directory)
        return self.extract_documents(documents)

    def extract_documents(self, documents: list[CorpusDocument]) -> dict[str, Any]:
        if not documents:
            raise FlowExtractionError("No supported corpus files found.")

        reasoning_context = ""
        if self.reasoning_service is not None:
            reasoning_context = self.reasoning_service.analyze(
                self._corpus_summary(documents)
            ).to_prompt_context()

        result = self.llm_client.complete_json(
            self._system_prompt(),
            self._user_content(documents, reasoning_context=reasoning_context),
        )
        return self.normalize_and_validate(result, source_paths=[str(doc.path) for doc in documents])

    def load_corpus(self, raw_directory: Path) -> list[CorpusDocument]:
        if raw_directory.is_file():
            paths = [raw_directory]
        else:
            paths = [
                path
                for path in sorted(raw_directory.rglob("*"))
                if path.is_file() and path.suffix.lower() in SUPPORTED_CORPUS_SUFFIXES
            ]

        documents = []
        for path in paths:
            suffix = path.suffix.lower()
            if suffix in TEXT_CORPUS_SUFFIXES:
                text = path.read_text(encoding="utf-8", errors="replace").strip()
                if text:
                    documents.append(CorpusDocument(path=path, text=text, kind="text"))
            elif suffix in IMAGE_CORPUS_SUFFIXES:
                documents.append(CorpusDocument(path=path, kind="image", data_url=self._image_data_url(path)))
            elif suffix == ".pdf":
                documents.extend(self._load_pdf(path))
            elif suffix == ".docx":
                text = self._extract_docx_text(path)
                if text:
                    documents.append(CorpusDocument(path=path, text=text, kind="docx"))
        return documents

    def _load_pdf(self, path: Path) -> list[CorpusDocument]:
        documents = []
        text = self._extract_pdf_text(path)
        if text:
            documents.append(CorpusDocument(path=path, text=text, kind="pdf_text"))

        # Scanned PDFs usually have little/no extractable text. If poppler is
        # installed, render a few pages and let the vision model read them.
        if not text or len(text) < 500:
            documents.extend(self._render_pdf_images(path))
        return documents

    def _extract_pdf_text(self, path: Path) -> str:
        if shutil.which("pdftotext") is None:
            return ""
        completed = subprocess.run(
            ["pdftotext", "-layout", str(path), "-"],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            return ""
        return completed.stdout.strip()

    def _render_pdf_images(self, path: Path) -> list[CorpusDocument]:
        if shutil.which("pdftoppm") is None or self.max_pdf_image_pages <= 0:
            return []

        with tempfile.TemporaryDirectory() as temp_dir:
            output_prefix = Path(temp_dir) / "page"
            completed = subprocess.run(
                [
                    "pdftoppm",
                    "-png",
                    "-f",
                    "1",
                    "-l",
                    str(self.max_pdf_image_pages),
                    str(path),
                    str(output_prefix),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if completed.returncode != 0:
                return []
            documents = []
            for image_path in sorted(Path(temp_dir).glob("page-*.png")):
                documents.append(
                    CorpusDocument(
                        path=Path(f"{path}#{image_path.stem}"),
                        kind="image",
                        data_url=self._image_data_url(image_path),
                    )
                )
            return documents

    def _image_data_url(self, path: Path) -> str:
        media_type = mimetypes.guess_type(path.name)[0] or "image/png"
        data = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:{media_type};base64,{data}"

    def _extract_docx_text(self, path: Path) -> str:
        try:
            with zipfile.ZipFile(path) as archive:
                raw_xml = archive.read("word/document.xml").decode("utf-8", errors="replace")
        except (KeyError, zipfile.BadZipFile, OSError):
            return ""
        text = re.sub(r"<w:tab\s*/>", "\t", raw_xml)
        text = re.sub(r"</w:p>", "\n", text)
        text = re.sub(r"<[^>]+>", "", text)
        text = (
            text.replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&quot;", '"')
            .replace("&apos;", "'")
        )
        return re.sub(r"\n\s*\n+", "\n", text).strip()

    def write_result(
        self,
        result: dict[str, Any],
        flow_directory: Path,
        user_task_directory: Path,
        action_registry_directory: Path | None = None,
        clean: bool = False,
    ) -> None:
        flow_directory.mkdir(parents=True, exist_ok=True)
        user_task_directory.mkdir(parents=True, exist_ok=True)
        if action_registry_directory is not None:
            action_registry_directory.mkdir(parents=True, exist_ok=True)
        if clean:
            for path in flow_directory.glob("*.flow.json"):
                path.unlink()
            for path in user_task_directory.glob("*.user_task.json"):
                path.unlink()
            if action_registry_directory is not None:
                for path in action_registry_directory.glob("*.registry.json"):
                    path.unlink()

        for user_task in result["user_tasks"]:
            target = user_task_directory / f"{user_task['user_task_id']}.user_task.json"
            target.write_text(json.dumps(user_task, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        for flow in result["flows"]:
            target = flow_directory / f"{flow['flow_id'].replace('.', '_')}.flow.json"
            target.write_text(json.dumps(flow, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        if action_registry_directory is not None:
            target = action_registry_directory / "actions.registry.json"
            target.write_text(
                json.dumps(result["action_registry"], ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

    def normalize_and_validate(self, result: dict[str, Any], source_paths: list[str]) -> dict[str, Any]:
        if not isinstance(result, dict):
            raise FlowExtractionError("LLM output must be a JSON object.")

        raw_user_tasks = result.get("user_tasks")
        raw_flows = result.get("flows")
        if not isinstance(raw_user_tasks, list) or not isinstance(raw_flows, list):
            raise FlowExtractionError("LLM output must contain 'user_tasks' and 'flows' arrays.")

        user_tasks = [self._normalize_user_task(item) for item in raw_user_tasks]
        task_ids = {task["user_task_id"] for task in user_tasks}

        flows = []
        for item in raw_flows:
            flow = self._normalize_flow(item, source_paths)
            missing_refs = [ref for ref in flow["user_task_refs"] if ref not in task_ids]
            if missing_refs:
                raise FlowExtractionError(
                    f"Flow {flow['flow_id']} references missing user tasks: {', '.join(missing_refs)}"
                )
            flows.append(flow)

        return {
            "user_tasks": sorted(user_tasks, key=lambda item: item["user_task_id"]),
            "flows": sorted(flows, key=lambda item: item["flow_id"]),
            "action_registry": self._build_action_registry(user_tasks, flows),
        }

    def _build_action_registry(
        self,
        user_tasks: list[dict[str, Any]],
        flows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        flows_by_task: dict[str, set[str]] = {}
        for flow in flows:
            for ref in flow["user_task_refs"]:
                flows_by_task.setdefault(ref, set()).add(flow["flow_id"])

        entries: dict[tuple[str, str], dict[str, Any]] = {}
        for user_task in user_tasks:
            task_id = user_task["user_task_id"]
            for action in [*user_task["front_actions"], *user_task["back_actions"]]:
                key = (action["type"], action["action"])
                entry = entries.setdefault(
                    key,
                    {
                        "action": action["action"],
                        "type": action["type"],
                        "operation": action.get("operation"),
                        "resource": action.get("resource"),
                        "label": action.get("label"),
                        "triggers": action.get("triggers"),
                        "description": action.get("description"),
                        "user_tasks": set(),
                        "flows": set(),
                    },
                )
                entry["user_tasks"].add(task_id)
                entry["flows"].update(flows_by_task.get(task_id, set()))

        registry = []
        for entry in entries.values():
            registry.append(
                {
                    **{
                        key: value
                        for key, value in entry.items()
                        if key not in {"user_tasks", "flows"}
                    },
                    "user_tasks": sorted(entry["user_tasks"]),
                    "flows": sorted(entry["flows"]),
                }
            )
        return sorted(registry, key=lambda item: (item["type"], item["action"]))

    def _normalize_user_task(self, item: dict[str, Any]) -> dict[str, Any]:
        required = {"user_task_id", "task", "type", "name", "description", "front_actions", "back_actions"}
        missing = required - set(item)
        if missing:
            raise FlowExtractionError(f"User task is missing required fields: {', '.join(sorted(missing))}")

        if self._looks_like_backend_operation(str(item["task"])) or self._looks_like_backend_operation(str(item["user_task_id"])):
            raise FlowExtractionError(
                f"'{item['task']}' looks like a backend operation. Put it under back_actions, not user_tasks."
            )
        user_task_id = self._slug(item["user_task_id"])
        task = self._slug(item["task"])

        front_actions = [
            self._normalize_action(action, expected_type="front_action")
            for action in item["front_actions"]
        ]
        back_actions = [
            self._normalize_action(action, expected_type="back_action")
            for action in item["back_actions"]
        ]
        if not back_actions:
            raise FlowExtractionError(f"User task {user_task_id} must include at least one back_action.")

        UserTask(
            user_task_id=user_task_id,
            task=task,
            type=item.get("type", "user_task"),
            name=str(item["name"]),
            description=str(item["description"]),
            front_actions=[Action(**action) for action in front_actions],
            back_actions=[Action(**action) for action in back_actions],
        )

        return {
            "user_task_id": user_task_id,
            "task": task,
            "type": item.get("type", "user_task"),
            "name": str(item["name"]),
            "description": str(item["description"]),
            "front_actions": front_actions,
            "back_actions": back_actions,
        }

    def _normalize_flow(self, item: dict[str, Any], source_paths: list[str]) -> dict[str, Any]:
        required = {
            "flow_id",
            "flow_name",
            "intent",
            "business_event",
            "utterances",
            "plan",
            "user_task_refs",
            "capabilities",
            "ontology_nodes",
            "explanation",
        }
        missing = required - set(item)
        if missing:
            raise FlowExtractionError(f"Flow is missing required fields: {', '.join(sorted(missing))}")

        refs = [self._slug(ref) for ref in item["user_task_refs"]]
        if not refs:
            raise FlowExtractionError(f"Flow {item['flow_id']} must include user_task_refs.")

        ontology_nodes = [str(value) for value in item["ontology_nodes"]]
        ontology_aliases = self.ontology_normalizer.build_aliases_for_ontology_nodes(ontology_nodes)

        return {
            "flow_id": self._flow_id(item["flow_id"]),
            "flow_name": str(item["flow_name"]),
            "intent": self._flow_id(item["intent"]),
            "business_event": str(item["business_event"]),
            "confidence": float(item.get("confidence", 0.75)),
            "utterances": [str(value) for value in item["utterances"]],
            "plan": [self._slug(value) for value in item["plan"]],
            "user_task_refs": refs,
            "capabilities": [self._operation_name(value) for value in item["capabilities"]],
            "ontology_nodes": ontology_nodes,
            "ontology_aliases": ontology_aliases,
            "explanation": str(item["explanation"]),
            "source": ";".join(source_paths),
            "metadata": {"generated_by": "llm_corpus_flow_loader", "source_files": source_paths},
        }

    def _normalize_action(self, item: dict[str, Any], expected_type: str) -> dict[str, Any]:
        required = {"action", "operation", "resource"}
        missing = required - set(item)
        if missing:
            raise FlowExtractionError(f"Action is missing required fields: {', '.join(sorted(missing))}")

        action = self._operation_name(item["action"])
        return {
            "action": action,
            "type": expected_type,
            "operation": self._slug(item["operation"]),
            "resource": self._slug(item["resource"]),
            "label": item.get("label"),
            "triggers": self._operation_name(item["triggers"]) if item.get("triggers") else None,
            "description": item.get("description"),
        }

    def _system_prompt(self) -> str:
        return (
            "You extract business process definitions from a mixed corpus. "
            "Return only valid JSON. Do not include markdown. "
            "A Flow is a business process. A UserTask is a human/business step. "
            "Technical CRUD, API, validation, notification, calculation, synchronization, "
            "or persistence operations must be back_actions, "
            "never user_tasks. Front actions are UI events that trigger backend actions. "
            "Infer all flow names, user tasks, resources, actions, ontology nodes, "
            "utterances, and business events only from the provided corpus. "
            "The application deterministically adds ontology_aliases/synonyms after extraction. "
            "The action registry is derived from front_actions and back_actions. "
            "Prefer reusable user_tasks across flows."
        )

    def _corpus_summary(self, documents: list[CorpusDocument]) -> str:
        lines = []
        for doc in documents:
            if doc.text:
                lines.append(f"{doc.path}: {doc.text[:2000]}")
            else:
                lines.append(f"{doc.path}: {doc.kind}")
        return "\n\n".join(lines)

    def _user_content(
        self,
        documents: list[CorpusDocument],
        reasoning_context: str = "",
    ) -> list[dict[str, Any]]:
        content: list[dict[str, Any]] = [{"type": "text", "text": self._schema_prompt()}]
        if reasoning_context:
            content.append({"type": "text", "text": reasoning_context})
        for doc in documents:
            if doc.kind == "image" and doc.data_url:
                content.append({"type": "text", "text": f"--- SOURCE IMAGE: {doc.path} ---"})
                content.append({"type": "image_url", "image_url": {"url": doc.data_url, "detail": "auto"}})
            else:
                content.append({"type": "text", "text": f"--- SOURCE: {doc.path} ---\n{doc.text[:12000]}"})
        return content

    def _schema_prompt(self) -> str:
        return (
            "Analyze this corpus and produce this exact JSON object:\n"
            "{\n"
            '  "user_tasks": [\n'
            "    {\n"
            '      "user_task_id": "verb_object",\n'
            '      "task": "verb_object",\n'
            '      "type": "user_task or approval",\n'
            '      "name": "Human readable name",\n'
            '      "description": "Business meaning",\n'
            '      "front_actions": [{"action": "ui.resource.event", "operation": "read|create|update|delete|calculate|validate|approve|notify", "resource": "resource", "label": "Button or screen action", "triggers": "resource.operation"}],\n'
            '      "back_actions": [{"action": "resource.operation", "operation": "read|create|update|delete|calculate|validate|approve|notify", "resource": "resource", "description": "Backend operation"}]\n'
            "    }\n"
            "  ],\n"
            '  "flows": [\n'
            "    {\n"
            '      "flow_id": "domain.process",\n'
            '      "flow_name": "Business process name",\n'
            '      "intent": "domain.intent",\n'
            '      "business_event": "BusinessEventName",\n'
            '      "confidence": 0.75,\n'
            '      "utterances": ["customer phrase"],\n'
            '      "plan": ["user_task_id"],\n'
            '      "user_task_refs": ["user_task_id"],\n'
            '      "capabilities": ["resource.operation"],\n'
            '      "ontology_nodes": ["EntityOrConcept"],\n'
            '      "explanation": "Why this flow exists"\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            "Extraction criteria:\n"
            "- Create flows for complete business processes or customer journeys.\n"
            "- Create user_tasks for business/user steps, not backend operations.\n"
            "- Put CRUD/calculation/API/checking operations under back_actions.\n"
            "- Put clicks/submits/views under front_actions.\n"
            "- Treat capabilities as action names; the final action registry will be built from every front_action and back_action.\n"
            "- Put formal concepts in ontology_nodes; do not manually add ontology_aliases because they are normalized by ingestion.\n"
            "- Include approval user tasks when the corpus says or implies approval/review/control is required.\n"
            "- If images are provided, first read their visible text and diagrams, then use that information together with the text files.\n"
            "- Do not invent fixed domain examples. Derive names and content from the corpus.\n\n"
            "Corpus files follow in this same message."
        )

    def _looks_like_backend_operation(self, value: str) -> bool:
        normalized = str(value).strip().lower().replace("_", ".")
        parts = normalized.split(".")
        if len(parts) < 2:
            return False
        return parts[-1] in TECHNICAL_OPERATION_SUFFIXES

    def _slug(self, value: Any) -> str:
        text = str(value).strip().lower()
        text = re.sub(r"[^a-z0-9_]+", "_", text)
        text = re.sub(r"_+", "_", text).strip("_")
        return text

    def _flow_id(self, value: Any) -> str:
        text = str(value).strip().lower()
        text = re.sub(r"[^a-z0-9_.]+", ".", text)
        text = re.sub(r"\.+", ".", text).strip(".")
        return text

    def _operation_name(self, value: Any) -> str:
        text = str(value).strip().lower()
        text = re.sub(r"[^a-z0-9_.]+", ".", text)
        text = re.sub(r"\.+", ".", text).strip(".")
        return text
