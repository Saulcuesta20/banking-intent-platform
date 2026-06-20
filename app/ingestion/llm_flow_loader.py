from __future__ import annotations

import base64
import hashlib
import json
import logging
import mimetypes
import os
import re
import shutil
import signal
import socket
import subprocess
import tempfile
import threading
import unicodedata
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from app.config.model import flow_extraction_prompt
from app.models import KnowledgeRecord, UserTask, _normalize_implementation_type
from app.knowledge_base.vocabulary import ConceptVocabulary
from app.tools.models import ToolDefinition


logger = logging.getLogger(__name__)

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

OPTIONAL_ASSET_ARRAYS = (
    "semantic_space",
    "domain",
    "module",
    "menu",
    "form",
    "form_version",
    "asset_set",
    "concept",
    "entity",
    "business_rule",
    "process",
    "plan",
    "qa",
    "causality",
)


def _normalize_free_text(value: str) -> str:
    text = unicodedata.normalize("NFKD", value)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _parse_json_content(content: str) -> dict[str, Any]:
    """Parse JSON from LLM content, stripping markdown code fences if present."""
    text = content.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return json.loads(text)


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
        timeout_seconds: int | None = None,
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("FLOW_EXTRACTOR_MODEL", "gpt-4o-mini")
        self.base_url = (base_url or os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        if self.base_url.endswith("/chat/completions"):
            self.base_url = self.base_url[: -len("/chat/completions")].rstrip("/")
        env_timeout = os.getenv("INTENT_LLM_TIMEOUT_SECONDS")
        if timeout_seconds is not None:
            self.timeout_seconds = timeout_seconds
        elif env_timeout:
            try:
                self.timeout_seconds = int(env_timeout)
            except ValueError:
                self.timeout_seconds = 90
        else:
            self.timeout_seconds = 90
        if "opencode.ai/zen" in self.base_url and timeout_seconds is None and not env_timeout:
            self.timeout_seconds = 45
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
        self.default_headers = self._default_headers()
        response_format = os.getenv("OPENAI_COMPATIBLE_RESPONSE_FORMAT")
        if response_format is None and "opencode.ai/zen" in self.base_url:
            self.include_response_format = False
        else:
            self.include_response_format = (response_format or "true").lower() != "false"

    def _default_headers(self) -> dict[str, str]:
        user_agent = os.getenv("OPENAI_COMPATIBLE_USER_AGENT", "curl/8.5.0")
        accept = os.getenv("OPENAI_COMPATIBLE_ACCEPT", "*/*")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": accept,
            "User-Agent": user_agent,
        }
        extra_headers = os.getenv("OPENAI_COMPATIBLE_EXTRA_HEADERS")
        if extra_headers:
            try:
                parsed = json.loads(extra_headers)
            except json.JSONDecodeError as exc:
                raise FlowExtractionError("OPENAI_COMPATIBLE_EXTRA_HEADERS must be valid JSON.") from exc
            if not isinstance(parsed, dict):
                raise FlowExtractionError("OPENAI_COMPATIBLE_EXTRA_HEADERS must be a JSON object.")
            for key, value in parsed.items():
                headers[str(key)] = str(value)
        return headers

    def complete_json(self, system_prompt: str, user_content: str | list[dict[str, Any]]) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
        }
        if self.include_response_format:
            payload["response_format"] = {"type": "json_object"}
        payload_bytes = json.dumps(payload).encode("utf-8")
        logger.info(
            "LLM request provider=openai_compatible base_url=%s model=%s timeout=%ss bytes=%s headers=%s",
            self.base_url,
            self.model,
            self.timeout_seconds,
            len(payload_bytes),
            {key: ("<redacted>" if key.lower() == "authorization" else value) for key, value in self.default_headers.items()},
        )
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=payload_bytes,
            headers=self.default_headers,
            method="POST",
        )
        try:
            raw = self._read_response(request)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise FlowExtractionError(f"LLM request failed: {exc.code} {detail}") from exc
        except urllib.error.URLError as exc:
            raise FlowExtractionError(f"LLM request failed: {exc.reason}") from exc
        except (TimeoutError, socket.timeout) as exc:
            raise FlowExtractionError(f"LLM request timed out after {self.timeout_seconds}s") from exc

        data = json.loads(raw)
        content = data["choices"][0]["message"]["content"]
        return _parse_json_content(content)

    def _read_response(self, request: urllib.request.Request) -> str:
        if threading.current_thread() is not threading.main_thread():
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                return response.read().decode("utf-8")

        def _timeout(_signum, _frame):
            raise TimeoutError(f"hard timeout after {self.timeout_seconds}s")

        previous_handler = signal.getsignal(signal.SIGALRM)
        signal.signal(signal.SIGALRM, _timeout)
        signal.setitimer(signal.ITIMER_REAL, float(self.timeout_seconds))
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                return response.read().decode("utf-8")
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous_handler)


class CorpusFlowLoader:
    max_batch_documents = 25
    max_batch_chars = 50_000
    max_document_chars = 18_000
    max_parallel_requests = 1

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
        self._configure_batch_limits()

    def _configure_batch_limits(self) -> None:
        base_url = getattr(self.llm_client, "base_url", "")
        if "opencode.ai/zen" in str(base_url):
            self.max_batch_documents = 1
            self.max_batch_chars = 3_000
            self.max_document_chars = 3_000
            self.max_parallel_requests = 3
        self.max_batch_documents = self._env_int("INGEST_LLM_MAX_BATCH_DOCUMENTS", self.max_batch_documents)
        self.max_batch_chars = self._env_int("INGEST_LLM_MAX_BATCH_CHARS", self.max_batch_chars)
        self.max_document_chars = self._env_int("INGEST_LLM_MAX_DOCUMENT_CHARS", self.max_document_chars)
        self.max_parallel_requests = self._env_int("INGEST_LLM_PARALLEL_REQUESTS", self.max_parallel_requests)

    @staticmethod
    def _env_int(name: str, default: int) -> int:
        raw = os.getenv(name)
        if not raw:
            return default
        try:
            value = int(raw)
        except ValueError:
            return default
        return value if value > 0 else default

    @staticmethod
    def _corpus_hash(documents: list[CorpusDocument]) -> str:
        """Compute a stable hash of all document texts for cache lookup."""
        h = hashlib.sha256()
        for doc in sorted(documents, key=lambda d: str(d.path)):
            h.update(str(doc.path).encode())
            h.update((doc.text or "").encode())
            h.update((doc.data_url or "").encode())
        return h.hexdigest()[:16]

    def _cache_path(self, cache_dir: Path, corpus_hash: str) -> Path:
        return cache_dir / f"{corpus_hash}.json"

    def _load_cache(self, cache_dir: Path, corpus_hash: str) -> dict[str, Any] | None:
        path = self._cache_path(cache_dir, corpus_hash)
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                return None
        return None

    def _save_cache(self, cache_dir: Path, corpus_hash: str, result: dict[str, Any]) -> None:
        cache_dir.mkdir(parents=True, exist_ok=True)
        path = self._cache_path(cache_dir, corpus_hash)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

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

        cache_dir = Path("data/processed/ingestion_cache")
        corpus_hash = self._corpus_hash(documents)
        cached = self._load_cache(cache_dir, corpus_hash)
        if cached is not None:
            return cached

        documents = self._chunk_large_documents(documents)

        if self._should_batch(documents):
            batches = self._batch_documents(documents)
            batch_results = self._extract_document_batches(
                batches,
                extraction_instructions_context=extraction_instructions_context,
            )
            result = self._merge_batch_results(batch_results)
        else:
            result = self.llm_client.complete_json(
                self._system_prompt(),
                self._user_content(documents, extraction_instructions_context=extraction_instructions_context),
            )
            result = self.normalize_and_validate(result, source_paths=[str(doc.path) for doc in documents])

        self._save_cache(cache_dir, corpus_hash, result)
        return result

    def _extract_document_batches(
        self,
        batches: list[list[CorpusDocument]],
        *,
        extraction_instructions_context: str = "",
    ) -> list[dict[str, Any]]:
        if self.max_parallel_requests <= 1 or len(batches) <= 1:
            return [
                self._extract_documents_batch(
                    batch,
                    extraction_instructions_context=extraction_instructions_context,
                )
                for batch in batches
            ]

        worker_count = min(self.max_parallel_requests, len(batches))
        logger.info(
            "Running %s LLM extraction batches with %s parallel workers",
            len(batches),
            worker_count,
        )
        results: list[dict[str, Any] | None] = [None] * len(batches)
        with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="ingest-llm") as executor:
            future_to_index = {
                executor.submit(
                    self._extract_documents_batch,
                    batch,
                    extraction_instructions_context=extraction_instructions_context,
                ): index
                for index, batch in enumerate(batches)
            }
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                results[index] = future.result()
        return [result for result in results if result is not None]

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

    def _extract_documents_batch(
        self,
        documents: list[CorpusDocument],
        *,
        extraction_instructions_context: str = "",
        _depth: int = 0,
    ) -> dict[str, Any]:
        try:
            result = self.llm_client.complete_json(
                self._system_prompt(),
                self._user_content(documents, extraction_instructions_context=extraction_instructions_context),
            )
            return self.normalize_and_validate(result, source_paths=[str(doc.path) for doc in documents])
        except json.JSONDecodeError:
            return self._split_and_retry_batch(
                documents,
                extraction_instructions_context=extraction_instructions_context,
                _depth=_depth,
            )
        except FlowExtractionError as exc:
            if not self._should_retry_batch_error(exc, documents):
                raise
            return self._split_and_retry_batch(
                documents,
                extraction_instructions_context=extraction_instructions_context,
                _depth=_depth,
            )

    def _split_and_retry_batch(
        self,
        documents: list[CorpusDocument],
        *,
        extraction_instructions_context: str = "",
        _depth: int = 0,
    ) -> dict[str, Any]:
        if len(documents) <= 1:
            return {
                "flows": [],
                "user_tasks": [],
                "tools": [],
                "entities": [],
                "_skipped": [str(doc.path) for doc in documents],
            }
        midpoint = max(1, len(documents) // 2)
        left = self._extract_documents_batch(
            documents[:midpoint],
            extraction_instructions_context=extraction_instructions_context,
            _depth=_depth + 1,
        )
        right = self._extract_documents_batch(
            documents[midpoint:],
            extraction_instructions_context=extraction_instructions_context,
            _depth=_depth + 1,
        )
        return self._merge_batch_results([left, right])

    def _should_retry_batch_error(self, exc: FlowExtractionError, documents: list[CorpusDocument]) -> bool:
        if not documents:
            return False
        reason = str(exc).lower()
        retryable_markers = (
            "timed out",
            "timeout",
            "connection reset",
            "request entity too large",
            "413",
            "403",
            "500",
            "502",
            "503",
            "504",
            "1010",
            "cloudflare",
            "context deadline",
            "internal server error",
            "bad gateway",
            "service unavailable",
            "gateway timeout",
        )
        if not any(marker in reason for marker in retryable_markers):
            return False
        return True

    def _chunk_large_documents(self, documents: list[CorpusDocument]) -> list[CorpusDocument]:
        if self.max_document_chars <= 0:
            return documents
        chunked: list[CorpusDocument] = []
        for document in documents:
            if document.data_url or len(document.text or "") <= self.max_document_chars:
                chunked.append(document)
                continue
            text = document.text
            for index, chunk in enumerate(self._split_text(text, self.max_document_chars), start=1):
                chunked.append(
                    CorpusDocument(
                        path=Path(f"{document.path}#chunk-{index}"),
                        text=chunk,
                        kind=document.kind,
                    )
                )
        if len(chunked) != len(documents):
            logger.info("Split %s corpus documents into %s LLM request chunks", len(documents), len(chunked))
        return chunked

    @staticmethod
    def _split_text(text: str, limit: int) -> list[str]:
        chunks: list[str] = []
        remaining = text
        while len(remaining) > limit:
            split_at = remaining.rfind("\n\n", 0, limit)
            if split_at < limit // 2:
                split_at = remaining.rfind("\n", 0, limit)
            if split_at < limit // 2:
                split_at = remaining.rfind(" ", 0, limit)
            if split_at < limit // 2:
                split_at = limit
            chunks.append(remaining[:split_at].strip())
            remaining = remaining[split_at:].strip()
        if remaining:
            chunks.append(remaining)
        return [chunk for chunk in chunks if chunk]

    def _should_batch(self, documents: list[CorpusDocument]) -> bool:
        if len(documents) > self.max_batch_documents:
            return True
        total_chars = sum(len(doc.text or "") + len(doc.data_url or "") for doc in documents)
        return total_chars > self.max_batch_chars

    def _batch_documents(self, documents: list[CorpusDocument]) -> list[list[CorpusDocument]]:
        batches: list[list[CorpusDocument]] = []
        current: list[CorpusDocument] = []
        current_chars = 0
        for document in documents:
            document_chars = len(document.text or "") + len(document.data_url or "")
            if current and (len(current) >= self.max_batch_documents or current_chars + document_chars > self.max_batch_chars):
                batches.append(current)
                current = []
                current_chars = 0
            current.append(document)
            current_chars += document_chars
        if current:
            batches.append(current)
        return batches

    def _merge_batch_results(self, batch_results: list[dict[str, Any]]) -> dict[str, Any]:
        merged_user_tasks: dict[str, dict[str, Any]] = {}
        merged_flows: dict[str, dict[str, Any]] = {}
        merged_optionals: dict[str, dict[str, Any]] = {key: {} for key in OPTIONAL_ASSET_ARRAYS}
        skipped: list[str] = []

        for result in batch_results:
            skipped.extend(str(path) for path in result.get("_skipped", []) if path)
            for user_task in result.get("user_tasks", []):
                if not isinstance(user_task, dict):
                    continue
                user_task_id = str(user_task.get("user_task_id") or "").strip()
                if not user_task_id:
                    continue
                existing = merged_user_tasks.get(user_task_id)
                merged_user_tasks[user_task_id] = self._prefer_richer_dict(existing, user_task)
            for flow in result.get("flows", []):
                if not isinstance(flow, dict):
                    continue
                flow_id = str(flow.get("flow_id") or "").strip()
                if not flow_id:
                    continue
                existing = merged_flows.get(flow_id)
                merged_flows[flow_id] = self._prefer_richer_dict(existing, flow)
            for key in OPTIONAL_ASSET_ARRAYS:
                for item in result.get(key, []):
                    if not isinstance(item, dict):
                        continue
                    identity = self._asset_identity(key, item)
                    if not identity:
                        continue
                    existing = merged_optionals[key].get(identity)
                    merged_optionals[key][identity] = self._prefer_richer_dict(existing, item)

        merged = {
            "user_tasks": sorted(merged_user_tasks.values(), key=lambda item: item["user_task_id"]),
            "flows": sorted(merged_flows.values(), key=lambda item: item["flow_id"]),
        }
        merged["tool_registry"] = self._build_tool_registry(merged["user_tasks"], merged["flows"])
        for key, values in merged_optionals.items():
            merged[key] = sorted(values.values(), key=lambda item: self._asset_sort_key(key, item))
        if skipped:
            merged["_skipped"] = sorted(set(skipped))
        return merged

    @staticmethod
    def _prefer_richer_dict(existing: dict[str, Any] | None, candidate: dict[str, Any]) -> dict[str, Any]:
        if existing is None:
            return dict(candidate)
        existing_score = sum(1 for value in existing.values() if value not in (None, "", [], {}))
        candidate_score = sum(1 for value in candidate.values() if value not in (None, "", [], {}))
        if candidate_score > existing_score:
            return dict(candidate)
        return dict(existing)

    @staticmethod
    def _asset_identity(key: str, item: dict[str, Any]) -> str:
        if key == "domain":
            return str(item.get("domain_id") or item.get("domainId") or item.get("name") or "").strip()
        if key == "module":
            return str(item.get("module_id") or item.get("moduleId") or item.get("name") or "").strip()
        if key == "menu":
            return str(item.get("menu_id") or item.get("menuId") or item.get("id") or item.get("name") or "").strip()
        if key == "form":
            return str(item.get("form_id") or item.get("formId") or item.get("name") or "").strip()
        if key == "form_version":
            return ":".join(
                [
                    str(item.get("form_id") or item.get("formId") or "").strip(),
                    str(item.get("version") or item.get("form_version") or item.get("formVersion") or "").strip(),
                ]
            ).strip(":")
        if key == "asset_set":
            return ":".join(
                [
                    str(item.get("asset_set_id") or item.get("assetSetId") or "").strip(),
                    str(item.get("version") or "").strip(),
                ]
            ).strip(":")
        if key == "entity":
            return str(item.get("entity_id") or item.get("name") or item.get("canonical_name") or "").strip()
        if key == "business_rule":
            return str(item.get("rule_id") or item.get("name") or item.get("business_rule_id") or "").strip()
        if key == "process":
            return str(item.get("process_id") or item.get("name") or "").strip()
        if key == "plan":
            return str(item.get("plan_id") or item.get("name") or "").strip()
        if key == "qa":
            return str(item.get("qa_id") or item.get("name") or "").strip()
        if key == "causality":
            return str(item.get("causality_id") or item.get("name") or item.get("cause") or "").strip()
        return str(item.get("name") or item.get("id") or "").strip()

    @staticmethod
    def _asset_sort_key(key: str, item: dict[str, Any]) -> str:
        identity = CorpusFlowLoader._asset_identity(key, item)
        return identity or json.dumps(item, sort_keys=True, ensure_ascii=False)

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
                user_actions=item.get("user_actions") or [],
                tools=[ToolDefinition(**tool) for tool in item.get("tools", [])],
            )
            for item in result.get("user_tasks", [])
        }
        records = []
        for flow in result.get("flows", []):
            user_tasks = [
                user_tasks_by_id[ref]
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
                    metadata={**flow.get("metadata", {}), "purpose": flow.get("purpose")},
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
            **self._optional_asset_arrays(result),
        }

    def _optional_asset_arrays(self, result: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
        assets: dict[str, list[dict[str, Any]]] = {}
        for key in OPTIONAL_ASSET_ARRAYS:
            value = result.get(key)
            if isinstance(value, list):
                assets[key] = [item for item in value if isinstance(item, dict)]
        return assets

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
        forbidden = [key for key in ("interaction_steps", "sequence", "operation", "resource") if key in item]
        if forbidden:
            raise FlowExtractionError(
                f"User task {item.get('user_task_id') or item.get('task')} uses deprecated fields: {', '.join(forbidden)}."
            )

        user_task_id = self._slug(item["user_task_id"])
        task = self._slug(item["task"])

        tools = self._normalize_tools(item)
        user_actions = self._normalize_user_actions(item, tools)

        UserTask(
            user_task_id=user_task_id,
            task=task,
            type=item.get("type", "user_task"),
            name=str(item["name"]),
            description=str(item["description"]),
            user_actions=user_actions,
            tools=[ToolDefinition(**tool) for tool in tools],
        )

        return {
            "user_task_id": user_task_id,
            "task": task,
            "type": item.get("type", "user_task"),
            "name": str(item["name"]),
            "description": str(item["description"]),
            "user_actions": user_actions,
            "tools": tools,
        }

    def _normalize_tools(self, item: dict[str, Any]) -> list[dict[str, Any]]:
        if isinstance(item.get("tools"), list):
            normalized_tools: list[dict[str, Any]] = []
            for tool in item["tools"]:
                if not isinstance(tool, dict):
                    continue
                try:
                    normalized_tools.append(self._normalize_tool(tool))
                except FlowExtractionError:
                    continue
            return normalized_tools
        tools = []
        for action in item.get("front_actions", []):
            if not isinstance(action, dict):
                continue
            try:
                tools.append(self._normalize_legacy_action(action, expected_type="front_action"))
            except FlowExtractionError:
                continue
        for action in item.get("back_actions", []):
            if not isinstance(action, dict):
                continue
            try:
                tools.append(self._normalize_legacy_action(action, expected_type="back_action"))
            except FlowExtractionError:
                continue
        return tools

    def _normalize_user_actions(self, item: dict[str, Any], tools: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
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
                implementation_type = _normalize_implementation_type(
                    implementation_type,
                    type_hint=normalized_type,
                    tool_id=str(action.get("tool_id") or action_id or ""),
                )
                tool_id = self._operation_name(action.get("tool_id")) if action.get("tool_id") else None
                tool_ids = []
                if isinstance(action.get("tool_ids"), list):
                    tool_ids = [self._operation_name(value) for value in action["tool_ids"] if str(value).strip()]
                elif tool_id:
                    tool_ids = [tool_id]
                values.append(
                    {
                        "action_id": action_id,
                        "type": normalized_type,
                        "implementation_type": implementation_type,
                        "lifecycle_state": str(action.get("lifecycle_state") or "not_started").strip() or "not_started",
                        "tool_id": tool_id,
                        "tool_ids": tool_ids,
                        "label": action.get("label"),
                        "triggers": self._operation_name(action["triggers"]) if action.get("triggers") else None,
                        "description": action.get("description"),
                    }
                )
            return values
        values: list[dict[str, Any]] = []
        for tool in (tools or self._normalize_tools(item)):
            tool_id = str(tool.get("tool_id") or "")
            if not tool_id:
                continue
            tool_type = str(tool.get("tool_type") or "")
            values.append(
                {
                    "action_id": tool_id,
                    "type": "front" if tool_type == "frontend_tool" else "back",
                    "implementation_type": "show_form" if tool_type == "frontend_tool" else ("llm_tool" if tool_type == "llm_tool" else "tool_call"),
                    "lifecycle_state": "not_started",
                    "tool_id": tool_id if tool_type != "frontend_tool" else None,
                    "tool_ids": [tool_id],
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
            "business_event",
            "explanation",
        }
        missing = required - set(item)
        if missing:
            raise FlowExtractionError(f"Flow is missing required fields: {', '.join(sorted(missing))}")

        raw_refs = item.get("user_task_refs") or item.get("user_tasks") or item.get("tasks") or item.get("user_task_ids") or []
        refs = [self._slug(ref) for ref in raw_refs]

        metadata = {"generated_by": "llm_corpus_flow_loader", "source_files": source_paths}

        return {
            "flow_id": self._flow_id(item["flow_id"]),
            "flow_name": str(item["flow_name"]),
            "purpose": str(item.get("purpose") or item.get("explanation") or item.get("flow_name") or item["flow_id"]),
            "intent": self._flow_id(item.get("intent") or item["flow_id"]),
            "business_event": str(item["business_event"]),
            "inputs": [self._slug(value) for value in item.get("inputs", []) if str(value).strip()],
            "outputs": [self._slug(value) for value in item.get("outputs", []) if str(value).strip()],
            "user_task_refs": refs,
            "explanation": str(item["explanation"]),
            "source": ";".join(source_paths),
            "metadata": metadata,
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
        base_url = str(getattr(self.llm_client, "base_url", ""))
        if "opencode.ai/zen" in base_url:
            return (
                "You extract banking assets from text. Return only valid compact JSON in the requested shape. "
                "No markdown. Do not invent facts. Empty arrays are allowed."
            )
        return (
            "You are an enterprise asset extractor for a banking platform. "
            "You extract governed asset candidates from a mixed corpus. "
            "Return only valid JSON. Do not include markdown.\n\n"

            "ASSET TYPE DEFINITIONS (use these to classify what you find):\n\n"

            "FLOW: A complete end-to-end business process that a company role executes "
            "to automate a banking transaction. A flow has multiple sequential steps "
            "(user tasks), involves decisions, validations, and state changes. "
            "Example: 'Loan Origination' (capture request → validate credit → approve → disburse). "
            "NOT a flow: a single question, a status check, an inquiry, or a one-step lookup.\n\n"

            "USER_TASK: A single human or system step within a flow. "
            "It has inputs, outputs, may invoke tools, and has a lifecycle state. "
            "Example: 'Capture Loan Request', 'Validate Customer Identity'.\n\n"

            "TOOL: A backend or frontend capability invoked by a user task. "
            "Backend tools: API calls, database operations, calculations. "
            "Frontend tools: UI events, form submissions, button clicks.\n\n"

            "ENTITY: A business or technical ontology element. "
            "Example: 'Customer', 'Loan', 'Account', 'Payment'. "
            "Entities have aliases, structural_layer, subtype, attributes, and relations to other entities. "
            "Use entity for new extraction; concept is only a legacy alias.\n\n"

            "BUSINESS_RULE: A conditional logic that governs behavior. "
            "Has conditions (when) and consequences (then). "
            "Example: 'If credit score < 600, require manual approval'.\n\n"

            "PROCESS: A technical implementation of a flow, more detailed than flow. "
            "Maps to executable system steps.\n\n"

            "PLAN: An orchestration plan that coordinates multiple flows or processes.\n\n"

            "QA: A question-answer pair from the corpus. "
            "Example: 'What documents are needed to open an account?'\n\n"

            "CAUSALITY: A cause-effect relationship between domain concepts. "
            "Example: 'Late payment causes delinquency'.\n\n"

            "SEMANTIC_SPACE: A search context for Ask and ontology navigation. "
            "It groups route_hints, structural_layers, allowed_asset_types, retrieval_policy, and related entities.\n\n"

            "CONTAINER ASSETS (domain, module, menu, form, form_version, asset_set): "
            "Structure and configuration of the banking platform launcher. Domain is legacy launcher metadata; "
            "use semantic_space for ontology search context.\n\n"

            "RULES FOR CLASSIFICATION:\n"
            "- If the corpus describes a MULTI-STEP process with roles, decisions, and automation → FLOW\n"
            "- If it describes a SINGLE human/system step → USER_TASK\n"
            "- If it describes a capability/tool to execute → TOOL\n"
            "- If it describes a domain noun/concept → ENTITY\n"
            "- If it describes conditional logic → BUSINESS_RULE\n"
            "- If it describes a question/answer → QA\n"
            "- If it describes cause/effect → CAUSALITY\n"
            "- If it describes a search/navigation context across layers and entities → SEMANTIC_SPACE\n"
            "- If it describes platform structure → CONTAINER ASSET\n\n"

            "Aliases belong to governed entity aliases, not concept_aliases. "
            "Classify entities with structural_layer: party, organization, capability, portfolio, offering, program, "
            "channel, transaction, agreement, event, metric, workforce, workforce_role, or business_resource. "
            "Infer all names, descriptions, and relationships from the corpus. "
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
    ) -> str | list[dict[str, Any]]:
        base_url = str(getattr(self.llm_client, "base_url", ""))
        if "opencode.ai/zen" in base_url and not any(doc.kind == "image" and doc.data_url for doc in documents):
            blocks = [self._schema_prompt()]
            if extraction_instructions_context:
                blocks.append(extraction_instructions_context)
            for doc in documents:
                blocks.append(f"--- SOURCE: {doc.path} ---\n{doc.text[: self.max_document_chars]}")
            return "\n\n".join(blocks)

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
        base_url = str(getattr(self.llm_client, "base_url", ""))
        if "opencode.ai/zen" in base_url:
            return self._compact_schema_prompt()
        return flow_extraction_prompt()

    def _compact_schema_prompt(self) -> str:
        return (
            "Return only JSON with arrays: flows, user_tasks, tools.\n"
            "Flow: flow_id, flow_name, business_event, explanation, purpose, intent, inputs, outputs, user_task_refs.\n"
            "User task: user_task_id, task, name, type, description, inputs, outputs, user_actions, tools.\n"
            "Tool: tool_id, tool_type, operation, resource, label, description, requires_approval.\n"
            "Use [] when none. Use lowercase snake_case or dot ids. Extract only grounded multi-step banking processes as flows."
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
