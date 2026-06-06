from __future__ import annotations

import json
import base64
import mimetypes
import os
import re
import shutil
import subprocess
import tempfile
import unicodedata
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from app.models import KnowledgeRecord, UserTask
from app.knowledge_base.vocabulary import ConceptVocabulary
from app.tools.models import ToolDefinition


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
    ".html",
    ".htm",
    ".yaml",
    ".yml",
    ".bpmn",
}


def _normalize_free_text(value: str) -> str:
    text = unicodedata.normalize("NFKD", value)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())

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


class ExtractionInstructionBuilder(Protocol):
    def build(self, corpus_summary: str) -> Any:
        """Build an object that can render prompt context."""


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
        self.tool_definition = ToolDefinition(
            tool_id="llm.corpus_flow_extraction.complete_json",
            tool_type="llm_tool",
            operation="extract_assets",
            resource="ingestion.corpus",
            label="Corpus flow extraction LLM",
            description="Extracts flows, user tasks, entities, and tools from raw enterprise corpus.",
            llm_operation="json_completion",
            llm_model=self.model,
            llm_provider="openai_compatible",
            endpoint=f"{self.base_url}/chat/completions",
        )
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
        instruction_builder: ExtractionInstructionBuilder | None = None,
        concept_vocabulary: ConceptVocabulary | None = None,
    ):
        self.llm_client = llm_client
        self.max_pdf_image_pages = max_pdf_image_pages
        self.instruction_builder = instruction_builder
        self.concept_vocabulary = concept_vocabulary or ConceptVocabulary()

    def extract(self, raw_directory: Path) -> dict[str, Any]:
        documents = self.load_corpus(raw_directory)
        return self.extract_documents(documents)

    def extract_documents(
        self,
        documents: list[CorpusDocument],
        extraction_instructions_context: str = "",
    ) -> dict[str, Any]:
        if not documents:
            raise FlowExtractionError("No supported corpus files found.")

        if not extraction_instructions_context and self.instruction_builder is not None:
            extraction_instructions_context = self.instruction_builder.build(
                self.corpus_summary(documents)
            ).to_prompt_context()

        result = self.llm_client.complete_json(
            self._system_prompt(),
            self._user_content(documents, extraction_instructions_context=extraction_instructions_context),
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

    def records_from_result(self, result: dict[str, Any], source: str = "ingestion_orchestrator") -> list[KnowledgeRecord]:
        user_tasks_by_id = {
            item["user_task_id"]: UserTask(
                user_task_id=item["user_task_id"],
                task=item["task"],
                type=item["type"],
                name=item.get("name"),
                description=item.get("description"),
                tools=[ToolDefinition(**tool) for tool in item.get("tools", [])],
            )
            for item in result.get("user_tasks", [])
        }
        records = []
        for flow in result.get("flows", []):
            user_tasks = [
                user_tasks_by_id[ref].model_copy(update={"sequence": index})
                for index, ref in enumerate(flow.get("user_task_refs", []), start=1)
                if ref in user_tasks_by_id
            ]
            records.append(
                KnowledgeRecord(
                    flow_id=flow["flow_id"],
                    flow_name=flow["flow_name"],
                    intent=flow["intent"],
                    confidence=flow.get("confidence", 0.75),
                    business_event=flow["business_event"],
                    utterances=flow.get("utterances", []),
                    plan=flow.get("plan", []),
                    tasks=[task.to_task() for task in user_tasks],
                    user_tasks=user_tasks,
                    capabilities=flow.get("capabilities", []),
                    concepts=flow.get("concepts", []),
                    concept_aliases=flow.get("concept_aliases", {}),
                    explanation=flow["explanation"],
                    source=flow.get("source", source),
                    metadata=flow.get("metadata", {}),
                )
            )
        return records

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
                for ref in missing_refs:
                    user_tasks.append(self._placeholder_user_task(ref, flow["flow_name"]))
                    task_ids.add(ref)
            flows.append(flow)

        return {
            "user_tasks": sorted(user_tasks, key=lambda item: item["user_task_id"]),
            "flows": sorted(flows, key=lambda item: item["flow_id"]),
            "tool_registry": self._build_tool_registry(user_tasks, flows),
        }

    def _build_tool_registry(
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
            for tool in user_task["tools"]:
                key = (tool["tool_type"], tool["tool_id"])
                entry = entries.setdefault(key, {**tool, "user_tasks": set(), "flows": set()})
                entry["user_tasks"].add(task_id)
                entry["flows"].update(flows_by_task.get(task_id, set()))

        registry = []
        for entry in entries.values():
            registry.append(
                {
                    **{key: value for key, value in entry.items() if key not in {"user_tasks", "flows"}},
                    "user_tasks": sorted(entry["user_tasks"]),
                    "flows": sorted(entry["flows"]),
                }
            )
        return sorted(registry, key=lambda item: (item["tool_type"], item["tool_id"]))

    def _placeholder_user_task(self, task_id: str, flow_name: str) -> dict[str, Any]:
        """Create a reviewable task when the LLM references a step but omits its definition."""
        name = str(task_id).replace("_", " ").title()
        return {
            "user_task_id": task_id,
            "task": task_id,
            "type": "user_task",
            "name": name,
            "description": f"Candidate user task inferred from flow {flow_name}.",
            "tools": [],
        }

    def _normalize_user_task(self, item: dict[str, Any]) -> dict[str, Any]:
        required = {"user_task_id", "task", "type", "name", "description"}
        missing = required - set(item)
        if missing:
            raise FlowExtractionError(f"User task is missing required fields: {', '.join(sorted(missing))}")

        if self._looks_like_backend_operation(str(item["task"])) or self._looks_like_backend_operation(str(item["user_task_id"])):
            raise FlowExtractionError(
                f"'{item['task']}' looks like a backend operation. Put it under tools as backend_tool, not user_tasks."
            )
        user_task_id = self._slug(item["user_task_id"])
        task = self._slug(item["task"])

        tools = self._normalize_tools(item)

        UserTask(
            user_task_id=user_task_id,
            task=task,
            type=item.get("type", "user_task"),
            name=str(item["name"]),
            description=str(item["description"]),
            user_actions=self._normalize_user_actions(item),
            interaction_steps=item.get("interaction_steps") or [],
            tools=[ToolDefinition(**tool) for tool in tools],
        )

        return {
            "user_task_id": user_task_id,
            "task": task,
            "type": item.get("type", "user_task"),
            "name": str(item["name"]),
            "description": str(item["description"]),
            "user_actions": self._normalize_user_actions(item),
            "interaction_steps": item.get("interaction_steps") or [],
            "tools": tools,
        }

    def _normalize_tools(self, item: dict[str, Any]) -> list[dict[str, Any]]:
        if isinstance(item.get("tools"), list):
            return [self._normalize_tool(tool) for tool in item["tools"]]
        tools = []
        tools.extend(
            self._normalize_legacy_action(action, expected_type="front_action")
            for action in item.get("front_actions", [])
        )
        tools.extend(
            self._normalize_legacy_action(action, expected_type="back_action")
            for action in item.get("back_actions", [])
        )
        return tools

    def _normalize_user_actions(self, item: dict[str, Any]) -> list[dict[str, Any]]:
        raw_actions = item.get("user_actions")
        if isinstance(raw_actions, list):
            values = []
            for action in raw_actions:
                if not isinstance(action, dict):
                    continue
                action_id = self._operation_name(action.get("action_id") or action.get("action") or "")
                if not action_id:
                    continue
                action_type = str(action.get("type") or "").strip().lower()
                if action_type in {"front_action", "front"}:
                    normalized_type = "front"
                else:
                    normalized_type = "back"
                implementation_type = str(action.get("implementation_type") or "").strip() or (
                    "show_form" if normalized_type == "front" else ("llm_tool" if "llm" in action_id else "tool_call")
                )
                values.append(
                    {
                        "action_id": action_id,
                        "type": normalized_type,
                        "implementation_type": implementation_type,
                        "tool_id": self._operation_name(action.get("tool_id")) if action.get("tool_id") else None,
                        "operation": self._slug(action["operation"]) if action.get("operation") else None,
                        "resource": self._slug(action["resource"]) if action.get("resource") else None,
                        "label": action.get("label"),
                        "triggers": self._operation_name(action["triggers"]) if action.get("triggers") else None,
                        "description": action.get("description"),
                    }
                )
            return values
        values: list[dict[str, Any]] = []
        for tool in self._normalize_tools(item):
            tool_id = str(tool.get("tool_id") or "")
            if not tool_id:
                continue
            tool_type = str(tool.get("tool_type") or "")
            values.append(
                {
                    "action_id": tool_id,
                    "type": "front" if tool_type == "frontend_tool" else "back",
                    "implementation_type": "show_form" if tool_type == "frontend_tool" else ("llm_tool" if tool_type == "llm_tool" else "tool_call"),
                    "tool_id": tool_id if tool_type != "frontend_tool" else None,
                    "operation": tool.get("operation"),
                    "resource": tool.get("resource"),
                    "label": tool.get("label"),
                    "triggers": tool.get("triggers") or tool.get("frontend_event"),
                    "description": tool.get("description"),
                }
            )
        return values

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
            "concepts",
            "explanation",
        }
        missing = required - set(item)
        if missing:
            raise FlowExtractionError(f"Flow is missing required fields: {', '.join(sorted(missing))}")

        refs = [self._slug(ref) for ref in item["user_task_refs"]]
        if not refs:
            raise FlowExtractionError(f"Flow {item['flow_id']} must include user_task_refs.")

        concepts = [str(value) for value in item["concepts"]]
        concept_aliases = self.concept_vocabulary.build_aliases_for_concepts(concepts)

        return {
            "flow_id": self._flow_id(item["flow_id"]),
            "flow_name": str(item["flow_name"]),
            "intent": self._flow_id(item["intent"]),
            "business_event": str(item["business_event"]),
            "confidence": float(item.get("confidence", 0.75)),
            "utterances": [str(value) for value in item["utterances"]],
            "inputs": [self._slug(value) for value in item.get("inputs", []) if str(value).strip()],
            "outputs": [self._slug(value) for value in item.get("outputs", []) if str(value).strip()],
            "plan": [self._slug(value) for value in item["plan"]],
            "user_task_refs": refs,
            "capabilities": [self._operation_name(value) for value in item["capabilities"]],
            "concepts": concepts,
            "concept_aliases": concept_aliases,
            "explanation": str(item["explanation"]),
            "source": ";".join(source_paths),
            "metadata": {"generated_by": "llm_corpus_flow_loader", "source_files": source_paths},
        }

    def _normalize_tool(self, item: dict[str, Any]) -> dict[str, Any]:
        required = {"tool_id", "tool_type", "operation", "resource"}
        missing = required - set(item)
        if missing:
            raise FlowExtractionError(f"Tool is missing required fields: {', '.join(sorted(missing))}")
        tool_type = str(item["tool_type"])
        if tool_type not in {"frontend_tool", "backend_tool", "llm_tool"}:
            raise FlowExtractionError(f"Unsupported tool_type: {tool_type}")
        raw = {
            "tool_id": self._operation_name(item["tool_id"]),
            "tool_type": tool_type,
            "operation": self._slug(item["operation"]),
            "resource": self._slug(item["resource"]),
            "label": item.get("label"),
            "description": item.get("description"),
            "triggers": self._operation_name(item["triggers"]) if item.get("triggers") else None,
            "frontend_event": self._operation_name(item["frontend_event"]) if item.get("frontend_event") else None,
            "backend_protocol": item.get("backend_protocol"),
            "endpoint": item.get("endpoint"),
            "llm_operation": item.get("llm_operation"),
            "llm_model": item.get("llm_model"),
            "llm_provider": item.get("llm_provider"),
            "requires_approval": bool(item.get("requires_approval", False)),
            "metadata": item.get("metadata", {}),
        }
        return {
            key: value
            for key, value in ToolDefinition(**{key: value for key, value in raw.items() if value is not None}).to_dict().items()
            if value not in (None, {}, [])
        }

    def _normalize_legacy_action(self, item: dict[str, Any], expected_type: str) -> dict[str, Any]:
        required = {"action", "operation", "resource"}
        missing = required - set(item)
        if missing:
            raise FlowExtractionError(f"Legacy tool is missing required fields: {', '.join(sorted(missing))}")

        action = self._operation_name(item["action"])
        return {
            "tool_id": action,
            "tool_type": "frontend_tool" if expected_type == "front_action" else "backend_tool",
            "operation": self._slug(item["operation"]),
            "resource": self._slug(item["resource"]),
            "label": item.get("label"),
            "triggers": self._operation_name(item["triggers"]) if item.get("triggers") else None,
            "frontend_event": self._operation_name(item["triggers"]) if expected_type == "front_action" and item.get("triggers") else None,
            "description": item.get("description"),
        }

    def _system_prompt(self) -> str:
        return (
            "You extract business process definitions from a mixed corpus. "
            "Return only valid JSON. Do not include markdown. "
            "A Flow is a business process. A UserTask is a human/business step. "
            "Technical CRUD, API, validation, notification, calculation, synchronization, "
            "or persistence operations must be backend tools, "
            "never user_tasks. Frontend tools are UI events that trigger backend tools. "
            "Infer all flow names, user tasks, resources, tools, concepts, "
            "utterances, and business events only from the provided corpus. "
            "The application deterministically adds concept_aliases/synonyms after extraction. "
            "The tool registry is derived from user task tools. "
            "Prefer reusable user_tasks across flows."
        )

    def corpus_summary(self, documents: list[CorpusDocument]) -> str:
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
        extraction_instructions_context: str = "",
    ) -> list[dict[str, Any]]:
        content: list[dict[str, Any]] = [{"type": "text", "text": self._schema_prompt()}]
        if extraction_instructions_context:
            content.append({"type": "text", "text": extraction_instructions_context})
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
            '      "user_actions": [\n'
            '        {"action_id": "action.resource.open_form", "type": "front", "implementation_type": "show_form", "label": "Open form"},\n'
            '        {"action_id": "tool.resource.create", "type": "back", "implementation_type": "tool_call", "tool_id": "tool.resource.create"}\n'
            '      ],\n'
            '      "interaction_steps": [\n'
            '        {"step_id": "task.front", "type": "user_action"},\n'
            '        {"step_id": "task.input", "type": "user_input", "wait_state": true},\n'
            '        {"step_id": "task.back.1", "type": "user_action"}\n'
            '      ],\n'
            '      "tools": [\n'
            '        {"tool_id": "ui.resource.event", "tool_type": "frontend_tool", "operation": "read|create|update|delete|calculate|validate|approve|notify", "resource": "resource", "label": "Button or screen action", "frontend_event": "resource.operation"},\n'
            '        {"tool_id": "resource.operation", "tool_type": "backend_tool", "operation": "read|create|update|delete|calculate|validate|approve|notify", "resource": "resource", "description": "Backend operation", "backend_protocol": "http|grpc|mcp|database"}\n'
            "      ]\n"
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
            '      "inputs": ["input_name"],\n'
            '      "outputs": ["output_name"],\n'
            '      "plan": ["user_task_id"],\n'
            '      "user_task_refs": ["user_task_id"],\n'
            '      "capabilities": ["resource.operation"],\n'
            '      "concepts": ["EntityOrConcept"],\n'
            '      "explanation": "Why this flow exists"\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            "Extraction criteria:\n"
            "- Create flows for complete business processes or customer journeys.\n"
            "- Create user_tasks for business/user steps, not backend operations.\n"
            "- Model each user_task as an interaction with user_actions and interaction_steps.\n"
            "- Typical interaction pattern is front user_action, then user_input wait_state, then back user_action.\n"
            "- Put CRUD/calculation/API/checking operations under backend_tool.\n"
            "- Put clicks/submits/views under frontend_tool.\n"
            "- Treat capabilities as tool ids; the final tool registry will be built from every tool.\n"
            "- Put formal concepts in concepts; do not manually add concept_aliases because they are normalized by ingestion.\n"
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
        if not text:
            return "unknown.flow"
        normalized = _normalize_free_text(text)
        phrase = f" {normalized} "
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
            if any(needle in phrase for needle in needles):
                return canonical
        text = re.sub(r"[^a-z0-9_.]+", ".", normalized)
        text = re.sub(r"\.+", ".", text).strip(".")
        return text or "unknown.flow"

    def _operation_name(self, value: Any) -> str:
        text = str(value).strip().lower()
        text = re.sub(r"[^a-z0-9_.]+", ".", text)
        text = re.sub(r"\.+", ".", text).strip(".")
        return text
