import json
import base64
import threading
import time
import zipfile
from pathlib import Path

import pytest

from app.ingestion.llm_flow_loader import (
    CorpusDocument,
    CorpusFlowLoader,
    FlowExtractionError,
    OpenAICompatibleLLMClient,
)
from app.ingestion.asset_pipeline import CanonicalAssetPipeline
from app.ingestion.orchestrator import IngestionOrchestratorConfig, IngestionOrchestratorService
from app.ingestion import orchestrator as ingestion_orchestrator
from app.ingestion.semantic_analyzer import SemanticAnalysisResult, SemanticChunkClassification
from app.knowledge_base.catalog_store import AssetCatalogStore
from app.knowledge_base.loader import AssetRegistryLoader
from app.knowledge_base.registry import EnterpriseAssetRegistry
from app.knowledge_base.vocabulary import ConceptVocabulary
from app.ingestion.orchestrator import (
    INGESTION_AGENT_SPECS,
    RoleBasedExtractionInstructionBuilder,
)


REGISTRY_PATH = Path(__file__).resolve().parents[1] / "config" / "asset_registry" / "asset_types.yaml"
RELATION_PATTERN_PATH = Path(__file__).resolve().parents[1] / "config" / "ingestion" / "relation_type_patterns.yaml"
ONTOLOGY_PATH = Path(__file__).resolve().parents[1] / "config" / "ontology" / "universal_layers.yaml"


class FakeLLMClient:
    def __init__(self, payload):
        self.payload = payload

    def complete_json(self, system_prompt: str, user_content):
        assert "enterprise asset extractor" in system_prompt.lower()
        assert isinstance(user_content, list)
        assert any(item.get("type") == "text" for item in user_content)
        return self.payload


class SequencedLLMClient:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.calls = 0

    def complete_json(self, system_prompt: str, user_content):
        payload = self.payloads[min(self.calls, len(self.payloads) - 1)]
        self.calls += 1
        return payload


class SplitRetryLLMClient:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.calls = 0

    def complete_json(self, system_prompt: str, user_content):
        self.calls += 1
        if self.calls == 1:
            raise json.JSONDecodeError("Expecting property name enclosed in double quotes", "{", 0)
        payload = self.payloads[min(self.calls - 2, len(self.payloads) - 1)]
        return payload


class TimeoutRetryLLMClient:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.calls = 0

    def complete_json(self, system_prompt: str, user_content):
        if self.calls == 0:
            self.calls += 1
            raise FlowExtractionError("LLM request failed: timed out")
        payload = self.payloads[min(self.calls - 1, len(self.payloads) - 1)]
        self.calls += 1
        return payload


class AlwaysTimeoutLLMClient:
    def __init__(self):
        self.calls = 0

    def complete_json(self, system_prompt: str, user_content):
        self.calls += 1
        raise FlowExtractionError("LLM request failed: timed out")


class ForbiddenLLMClient:
    def complete_json(self, system_prompt: str, user_content):
        raise FlowExtractionError("LLM request failed: 403 Cloudflare")


class InternalServerErrorLLMClient:
    def complete_json(self, system_prompt: str, user_content):
        raise FlowExtractionError("LLM request failed: 500 Internal server error")


class ParallelLLMClient:
    base_url = "https://opencode.ai/zen/v1"

    def __init__(self):
        self.calls = 0
        self.max_active = 0
        self._active = 0
        self._lock = threading.Lock()

    def complete_json(self, system_prompt: str, user_content):
        match = None
        if isinstance(user_content, str):
            import re

            match = re.search(r"doc-(\d+)\.txt", user_content)
        document_number = int(match.group(1)) if match else 0
        with self._lock:
            self.calls += 1
            self._active += 1
            self.max_active = max(self.max_active, self._active)
        time.sleep(0.05)
        try:
            payload = valid_payload()
            payload["flows"][0]["flow_id"] = f"parallel.case.{document_number}"
            payload["flows"][0]["flow_name"] = f"Parallel Case {document_number}"
            payload["flows"][0]["user_task_refs"] = [f"review_parallel_case_{document_number}"]
            payload["user_tasks"][0]["user_task_id"] = f"review_parallel_case_{document_number}"
            payload["user_tasks"][0]["task"] = f"review_parallel_case_{document_number}"
            return payload
        finally:
            with self._lock:
                self._active -= 1


class CountingInstructionBuilder:
    def __init__(self):
        self.calls = 0

    def build(self, corpus_summary: str):
        self.calls += 1

        class _Context:
            def to_prompt_context(self_inner):
                return "role instructions"

        return _Context()


def fake_graph_module():
    class FakeCompiledGraph:
        def __init__(self, builder):
            self.builder = builder

        def invoke(self, state):
            current = self.builder.start
            while current != "__end__":
                update = self.builder.nodes[current](state)
                state.update(update)
                route = self.builder.conditional_edges.get(current)
                if route:
                    route_value = route["path"](state)
                    current = route["path_map"][route_value]
                else:
                    current = self.builder.edges[current]
            return state

    class FakeStateGraph:
        def __init__(self, state_schema):
            self.state_schema = state_schema
            self.nodes = {}
            self.edges = {}
            self.conditional_edges = {}
            self.start = None

        def add_node(self, name, action):
            self.nodes[name] = action

        def add_edge(self, source, target):
            if source == "__start__":
                self.start = target
            else:
                self.edges[source] = target

        def add_conditional_edges(self, source, path, path_map):
            self.conditional_edges[source] = {"path": path, "path_map": path_map}

        def compile(self):
            return FakeCompiledGraph(self)

    class FakeGraphModule:
        StateGraph = FakeStateGraph
        START = "__start__"
        END = "__end__"

    return FakeGraphModule


def valid_payload():
    return {
        "user_tasks": [
            {
                "user_task_id": "review_refinance_options",
                "task": "review_refinance_options",
                "type": "user_task",
                "name": "Review Refinance Options",
                "description": "Review refinance choices with the customer.",
                "tools": [
                    {
                        "tool_id": "ui.refinance.calculate",
                        "tool_type": "frontend_tool",
                        "operation": "calculate",
                        "resource": "loan_refinance",
                        "label": "Calculate refinance",
                        "frontend_event": "loan_refinance.calculate",
                    },
                    {
                        "tool_id": "loan.conditions.calculate",
                        "tool_type": "backend_tool",
                        "operation": "calculate",
                        "resource": "loan",
                        "description": "Calculate new loan conditions.",
                    },
                ],
            }
        ],
        "flows": [
            {
                "flow_id": "loan.refinance",
                "flow_name": "Loan Refinance",
                "purpose": "Help a customer request refinancing for an existing loan.",
                "business_event": "LoanRefinancingRequested",
                "inputs": ["loan_id"],
                "outputs": ["refinance_result"],
                "user_task_refs": ["review_refinance_options"],
                "explanation": "The corpus describes refinance options.",
            }
        ],
    }


def test_corpus_flow_loader_extracts_and_validates(tmp_path: Path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "domain.txt").write_text("Refinanciacion de prestamo", encoding="utf-8")

    loader = CorpusFlowLoader(FakeLLMClient(valid_payload()))
    result = loader.extract(raw_dir)

    assert result["flows"][0]["flow_id"] == "loan.refinance"
    assert result["flows"][0]["purpose"] == "Help a customer request refinancing for an existing loan."
    assert result["flows"][0]["intent"] == "loan.refinance"
    assert result["flows"][0]["user_task_refs"] == ["review_refinance_options"]
    assert "concept_aliases" not in result["flows"][0]
    assert result["user_tasks"][0]["tools"][1]["tool_id"] == "loan.conditions.calculate"
    assert result["user_tasks"][0]["user_actions"][1]["tool_ids"] == ["loan.conditions.calculate"]
    assert result["tool_registry"] == [
        {
            "tool_id": "loan.conditions.calculate",
            "tool_type": "backend_tool",
            "operation": "calculate",
            "resource": "loan",
            "description": "Calculate new loan conditions.",
            "requires_approval": False,
            "user_tasks": ["review_refinance_options"],
            "flows": ["loan.refinance"],
        },
        {
            "tool_id": "ui.refinance.calculate",
            "tool_type": "frontend_tool",
            "operation": "calculate",
            "resource": "loan_refinance",
            "label": "Calculate refinance",
            "frontend_event": "loan_refinance.calculate",
            "requires_approval": False,
            "user_tasks": ["review_refinance_options"],
            "flows": ["loan.refinance"],
        },
    ]


def test_corpus_flow_loader_accepts_flow_task_fallbacks(tmp_path: Path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "domain.txt").write_text("Refinanciacion de prestamo", encoding="utf-8")
    payload = valid_payload()
    payload["flows"][0].pop("user_task_refs")
    payload["flows"][0]["user_tasks"] = ["review_refinance_options"]

    result = CorpusFlowLoader(FakeLLMClient(payload)).extract(raw_dir)

    assert result["flows"][0]["user_task_refs"] == ["review_refinance_options"]


def test_corpus_flow_loader_allows_flows_without_explicit_task_refs(tmp_path: Path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "domain.txt").write_text("Refinanciacion de prestamo", encoding="utf-8")
    payload = valid_payload()
    payload["flows"][0].pop("user_task_refs")
    payload["flows"][0].pop("user_tasks", None)
    payload["flows"][0].pop("tasks", None)
    payload["flows"][0].pop("user_task_ids", None)

    result = CorpusFlowLoader(FakeLLMClient(payload)).extract(raw_dir)

    assert result["flows"][0]["user_task_refs"] == []


def test_corpus_flow_loader_preserves_unified_asset_arrays(tmp_path: Path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "domain.txt").write_text("Refinanciacion de prestamo", encoding="utf-8")
    payload = valid_payload()
    payload["domain"] = [{"domain_id": "lending", "name": "Lending", "purpose": "Loan products"}]
    payload["module"] = [{"module_id": "loan", "domain_id": "lending", "name": "Loan", "purpose": "Loan operations"}]
    payload["entity"] = [{"name": "Prestamo", "aliases": ["credito"]}]
    payload["business_rule"] = [
        {
            "name": "Elegibilidad de refinanciamiento",
            "when": "loan.refinance.requested",
            "then": "validate eligibility",
            "conditions": ["loan is active"],
            "consequences": ["refinance may continue"],
            "applies_to": ["flow.loan.refinance"],
        }
    ]
    payload["process"] = [
        {
            "name": "Refinanciamiento",
            "business_event": "loan.refinance.requested",
            "execution_nodes": [{"node_id": "start", "type": "start", "name": "Start"}],
        }
    ]

    result = CorpusFlowLoader(FakeLLMClient(payload)).extract(raw_dir)

    assert result["entity"][0]["name"] == "Prestamo"
    assert result["domain"][0]["domain_id"] == "lending"
    assert result["module"][0]["module_id"] == "loan"
    assert result["business_rule"][0]["when"] == "loan.refinance.requested"
    assert result["process"][0]["business_event"] == "loan.refinance.requested"


def test_corpus_flow_loader_normalizes_service_invocation_action_type(tmp_path: Path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "domain.txt").write_text("Refinanciacion de prestamo", encoding="utf-8")
    payload = valid_payload()
    payload["user_tasks"][0]["user_actions"] = [
        {
            "action_id": "open_refinance_panel",
            "type": "front",
            "implementation_type": "service_invocation",
            "label": "Open refinance panel",
            "description": "Open the refinance panel",
        }
    ]

    result = CorpusFlowLoader(FakeLLMClient(payload)).extract(raw_dir)

    assert result["user_tasks"][0]["user_actions"][0]["implementation_type"] == "service_call"


def test_corpus_flow_loader_loads_images_as_llm_visual_content(tmp_path: Path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    tiny_png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
    )
    (raw_dir / "diagram.png").write_bytes(tiny_png)

    loader = CorpusFlowLoader(FakeLLMClient(valid_payload()))
    documents = loader.load_corpus(raw_dir)
    content = loader._user_content(documents)

    assert documents[0].kind == "image"
    assert any(item.get("type") == "image_url" for item in content)


def test_concept_vocabulary_maps_synonyms_to_canonical_terms():
    normalizer = ConceptVocabulary()

    normalized = normalizer.normalize_term("credito")
    expanded = normalizer.expand_search_terms(["credito"])

    assert normalized.canonical == "loan"
    assert "prestamo" in normalized.aliases
    assert "loan" in expanded
    assert "credito" in expanded


def test_corpus_flow_loader_extracts_docx_text(tmp_path: Path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    docx_path = raw_dir / "domain.docx"
    with zipfile.ZipFile(docx_path, "w") as archive:
        archive.writestr(
            "word/document.xml",
            "<w:document><w:body><w:p><w:r><w:t>Refinanciacion de prestamo</w:t></w:r></w:p></w:body></w:document>",
        )

    loader = CorpusFlowLoader(FakeLLMClient(valid_payload()))
    documents = loader.load_corpus(raw_dir)

    assert documents[0].kind == "docx"
    assert documents[0].text == "Refinanciacion de prestamo"


def test_corpus_flow_loader_adds_ingestion_extraction_instructions_context(tmp_path: Path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "domain.txt").write_text("Refinanciacion de prestamo", encoding="utf-8")

    class InspectingLLMClient(FakeLLMClient):
        def complete_json(self, system_prompt: str, user_content):
            assert any(
                "ValidatorAgent" in item.get("text", "")
                for item in user_content
                if item.get("type") == "text"
            )
            return super().complete_json(system_prompt, user_content)

    loader = CorpusFlowLoader(
        InspectingLLMClient(valid_payload()),
        instruction_builder=RoleBasedExtractionInstructionBuilder(),
    )
    result = loader.extract(raw_dir)

    assert result["flows"][0]["flow_id"] == "loan.refinance"


def test_corpus_flow_loader_batches_large_corpus_and_merges_results(tmp_path: Path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    for index in range(30):
        (raw_dir / f"doc-{index}.txt").write_text(f"Document {index} with enough content to trigger batching and push over the 25 document limit.", encoding="utf-8")

    payload_one = valid_payload()
    payload_one["flows"][0]["flow_id"] = "alpha.case.one"
    payload_one["flows"][0]["flow_name"] = "Alpha Case One"
    payload_one["flows"][0]["user_task_refs"] = ["review_case_one"]
    payload_one["user_tasks"][0]["user_task_id"] = "review_case_one"
    payload_one["user_tasks"][0]["task"] = "review_case_one"

    payload_two = valid_payload()
    payload_two["flows"][0]["flow_id"] = "beta.case.two"
    payload_two["flows"][0]["flow_name"] = "Beta Case Two"
    payload_two["flows"][0]["user_task_refs"] = ["review_case_two"]
    payload_two["user_tasks"][0]["user_task_id"] = "review_case_two"
    payload_two["user_tasks"][0]["task"] = "review_case_two"

    result = CorpusFlowLoader(SequencedLLMClient([payload_one, payload_two])).extract(raw_dir)

    assert len(result["flows"]) == 2
    assert len(result["user_tasks"]) == 2
    assert result["tool_registry"]
    assert result["flows"][0]["flow_id"] == "alpha.case.one"
    assert result["flows"][1]["flow_id"] == "beta.case.two"


def test_corpus_flow_loader_can_run_batches_in_parallel(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("INGEST_LLM_PARALLEL_REQUESTS", "3")
    monkeypatch.setenv("INGEST_LLM_MAX_BATCH_DOCUMENTS", "1")
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    for index in range(4):
        (raw_dir / f"doc-{index}.txt").write_text(
            f"Document {index} with enough content to trigger one-document batches.",
            encoding="utf-8",
        )

    client = ParallelLLMClient()
    result = CorpusFlowLoader(client).extract(raw_dir)

    assert client.calls == 4
    assert client.max_active > 1
    assert [flow["flow_id"] for flow in result["flows"]] == [
        "parallel.case.0",
        "parallel.case.1",
        "parallel.case.2",
        "parallel.case.3",
    ]


def test_corpus_flow_loader_builds_instruction_context_once_for_batched_runs(tmp_path: Path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    for index in range(13):
        (raw_dir / f"doc-{index}.txt").write_text(f"Document {index} with enough content to trigger batching.", encoding="utf-8")

    builder = CountingInstructionBuilder()
    loader = CorpusFlowLoader(SequencedLLMClient([valid_payload(), valid_payload()]), instruction_builder=builder)
    loader.extract(raw_dir)

    assert builder.calls == 1


def test_corpus_flow_loader_splits_batches_after_invalid_json(tmp_path: Path):
    payload_one = valid_payload()
    payload_one["flows"][0]["flow_id"] = "alpha.case.one"
    payload_one["flows"][0]["flow_name"] = "Alpha Case One"
    payload_one["flows"][0]["user_task_refs"] = ["review_case_one"]
    payload_one["user_tasks"][0]["user_task_id"] = "review_case_one"
    payload_one["user_tasks"][0]["task"] = "review_case_one"

    payload_two = valid_payload()
    payload_two["flows"][0]["flow_id"] = "beta.case.two"
    payload_two["flows"][0]["flow_name"] = "Beta Case Two"
    payload_two["flows"][0]["user_task_refs"] = ["review_case_two"]
    payload_two["user_tasks"][0]["user_task_id"] = "review_case_two"
    payload_two["user_tasks"][0]["task"] = "review_case_two"

    client = SplitRetryLLMClient([payload_one, payload_two])
    loader = CorpusFlowLoader(client)
    documents = [
        CorpusDocument(path=tmp_path / "doc-0.txt", text="Document 0 with enough content to trigger batching."),
        CorpusDocument(path=tmp_path / "doc-1.txt", text="Document 1 with enough content to trigger batching."),
    ]
    result = loader._extract_documents_batch(documents)

    assert client.calls >= 3
    assert [flow["flow_id"] for flow in result["flows"]] == ["alpha.case.one", "beta.case.two"]


def test_corpus_flow_loader_retries_batches_after_timeout(tmp_path: Path):
    payload_one = valid_payload()
    payload_one["flows"][0]["flow_id"] = "alpha.case.one"
    payload_one["flows"][0]["flow_name"] = "Alpha Case One"
    payload_one["flows"][0]["user_task_refs"] = ["review_case_one"]
    payload_one["user_tasks"][0]["user_task_id"] = "review_case_one"
    payload_one["user_tasks"][0]["task"] = "review_case_one"

    payload_two = valid_payload()
    payload_two["flows"][0]["flow_id"] = "beta.case.two"
    payload_two["flows"][0]["flow_name"] = "Beta Case Two"
    payload_two["flows"][0]["user_task_refs"] = ["review_case_two"]
    payload_two["user_tasks"][0]["user_task_id"] = "review_case_two"
    payload_two["user_tasks"][0]["task"] = "review_case_two"

    client = TimeoutRetryLLMClient([payload_one, payload_two])
    loader = CorpusFlowLoader(client)
    documents = [
        CorpusDocument(path=tmp_path / "doc-0.txt", text="Document 0"),
        CorpusDocument(path=tmp_path / "doc-1.txt", text="Document 1"),
    ]

    result = loader._extract_documents_batch(documents)

    assert client.calls == 3
    assert [flow["flow_id"] for flow in result["flows"]] == ["alpha.case.one", "beta.case.two"]


def test_corpus_flow_loader_skips_documents_after_repeated_timeouts(tmp_path: Path):
    loader = CorpusFlowLoader(AlwaysTimeoutLLMClient())
    documents = [CorpusDocument(path=tmp_path / "doc-0.txt", text="Document 0")]

    result = loader._extract_documents_batch(documents)

    assert result["flows"] == []
    assert result["user_tasks"] == []
    assert result.get("_skipped") == [str(documents[0].path)]


def test_corpus_flow_loader_retries_cloudflare_errors_by_splitting_batches(tmp_path: Path):
    loader = CorpusFlowLoader(ForbiddenLLMClient())
    documents = [
        CorpusDocument(path=tmp_path / "doc-0.txt", text="Document 0"),
        CorpusDocument(path=tmp_path / "doc-1.txt", text="Document 1"),
    ]

    result = loader._extract_documents_batch(documents)

    assert result["flows"] == []
    assert result["user_tasks"] == []
    assert result.get("_skipped") == [str(documents[0].path), str(documents[1].path)]


def test_corpus_flow_loader_skips_documents_after_provider_500(tmp_path: Path):
    loader = CorpusFlowLoader(InternalServerErrorLLMClient())
    documents = [CorpusDocument(path=tmp_path / "doc-0.txt", text="Document 0")]

    result = loader._extract_documents_batch(documents)

    assert result["flows"] == []
    assert result["user_tasks"] == []
    assert result.get("_skipped") == [str(documents[0].path)]


def test_corpus_flow_loader_chunks_large_documents_for_opencode_profile(tmp_path: Path):
    client = type("Client", (), {"base_url": "https://opencode.ai/zen/v1", "complete_json": lambda *_args: valid_payload()})()
    loader = CorpusFlowLoader(client)
    documents = [
        CorpusDocument(path=tmp_path / "large.txt", text=("abc " * 4000).strip()),
    ]

    chunked = loader._chunk_large_documents(documents)

    assert len(chunked) > 1
    assert all("#chunk-" in str(document.path) for document in chunked)
    assert all(len(document.text) <= loader.max_document_chars for document in chunked)


def test_openai_compatible_client_uses_curl_like_headers(monkeypatch):
    monkeypatch.delenv("OPENAI_COMPATIBLE_EXTRA_HEADERS", raising=False)
    client = OpenAICompatibleLLMClient(
        api_key="test-key",
        model="deepseek-v4-pro",
        base_url="https://opencode.ai/zen/v1/chat/completions",
    )

    assert client.base_url == "https://opencode.ai/zen/v1"
    assert client.default_headers["User-Agent"] == "curl/8.5.0"
    assert client.default_headers["Accept"] == "*/*"
    assert client.default_headers["Content-Type"] == "application/json"
    assert client.include_response_format is False


def test_semantic_analysis_prompt_context_is_compact():
    result = SemanticAnalysisResult(
        summary="Heuristic corpus summary",
        review_required=True,
        classifications=[
            SemanticChunkClassification(
                source=f"doc-{index}.md",
                intent_class="approval",
                processes=["loan.application", "money.transfer"],
                systems=["loan_origination"],
                confidence=0.45,
                evidence="x" * 300,
                needs_human_review=True,
                review_reason="mixed",
            )
            for index in range(10)
        ],
    )

    context = result.to_prompt_context()

    assert "Heuristic corpus summary" in context
    assert "doc-0.md" in context
    assert "... 2 more classifications omitted for brevity" in context
    assert len(context) < 4000


def test_ingestion_orchestrator_previews_extraction_and_audit(tmp_path: Path, monkeypatch):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "domain.txt").write_text("Refinanciacion de prestamo", encoding="utf-8")

    monkeypatch.setattr(
        IngestionOrchestratorService,
        "_optional_import",
        lambda self, module_name, friendly_name: fake_graph_module(),
    )

    orchestrator = IngestionOrchestratorService(CorpusFlowLoader(FakeLLMClient(valid_payload())))
    result = orchestrator.run(
        IngestionOrchestratorConfig(
            raw_path=raw_dir,
            audit_directory=tmp_path / "audit",
            extraction_instruction_mode="none",
        )
    )

    assert result.mode == "preview"
    assert result.flows_persisted == 0
    assert result.user_tasks_extracted == 1
    assert result.tools_extracted == 2
    assert result.audit_path.exists()
    assert result.asset_analysis["asset_types"]["flow"]["candidate_count"] == 1
    assert result.asset_analysis["payloads"]["flow"]["status"] == "candidate_payload_available"
    assert result.asset_analysis["relationships"]
    audit_text = result.audit_path.read_text(encoding="utf-8")
    assert "scan_and_parse_corpus" in audit_text
    assert "analyze_semantics_classify_corpus" in audit_text
    assert "classify_asset_types" in audit_text
    assert "resolve_aliases_and_similarity" in audit_text
    assert "hydrate_asset_payloads" in audit_text
    assert "normalize_asset_relationships" in audit_text
    assert "prepare_human_review_actions" in audit_text
    assert "write_audit" in audit_text


def test_ingestion_orchestrator_runs_nodes_with_graph_orchestrator(tmp_path: Path, monkeypatch):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "domain.txt").write_text("Refinanciacion de prestamo", encoding="utf-8")

    monkeypatch.setattr(
        ingestion_orchestrator.IngestionOrchestratorService,
        "_optional_import",
        lambda self, module_name, friendly_name: fake_graph_module(),
    )

    orchestrator = ingestion_orchestrator.IngestionOrchestratorService(
        CorpusFlowLoader(FakeLLMClient(valid_payload()))
    )
    result = orchestrator.run(
        IngestionOrchestratorConfig(
            raw_path=raw_dir,
            audit_directory=tmp_path / "audit",
            extraction_instruction_mode="none",
            max_validation_retries=1,
            require_human_review=True,
        )
    )

    assert result.user_tasks_extracted == 1
    assert any(step["owner"] == "langgraph" for step in result.steps)
    assert any(step["name"] == "prepare_human_review_actions" for step in result.steps)
    assert "requires_human_review" in result.audit_path.read_text(encoding="utf-8")


def test_ingestion_orchestrator_generates_and_persists_canonical_catalog_assets(tmp_path: Path, monkeypatch):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "domain.txt").write_text("Refinanciacion de prestamo", encoding="utf-8")
    payload = valid_payload()
    payload["domain"] = [{"domain_id": "lending", "name": "Lending", "purpose": "Loan products"}]
    payload["module"] = [{"module_id": "loan", "domain_id": "lending", "name": "Loan", "purpose": "Loan operations"}]

    monkeypatch.setattr(
        ingestion_orchestrator.IngestionOrchestratorService,
        "_optional_import",
        lambda self, module_name, friendly_name: fake_graph_module(),
    )

    registry = EnterpriseAssetRegistry(AssetRegistryLoader().load_file(REGISTRY_PATH))
    catalog = AssetCatalogStore(tmp_path / "catalog.sqlite")
    orchestrator = ingestion_orchestrator.IngestionOrchestratorService(
        CorpusFlowLoader(FakeLLMClient(payload)),
        canonical_asset_pipeline=CanonicalAssetPipeline(
            registry=registry,
            relation_pattern_path=RELATION_PATTERN_PATH,
            ontology_path=ONTOLOGY_PATH,
        ),
    )

    result = orchestrator.run(
        IngestionOrchestratorConfig(
            raw_path=raw_dir,
            audit_directory=tmp_path / "audit",
            asset_staging_directory=tmp_path / "staging",
            asset_catalog_store=catalog,
            asset_registry=registry,
            extraction_instruction_mode="none",
            apply=True,
        )
    )

    assert result.canonical_assets_generated > 0
    assert result.catalog_assets_persisted == result.canonical_assets_generated
    assert result.staged_asset_sets
    assert all(Path(item["manifest_path"]).is_file() for item in result.staged_asset_sets)
    assert catalog.list_asset_sets(status="ready_for_review")
    assert catalog.get_asset("domain.lending")["asset_type"] == "domain"
    assert catalog.get_asset("module.loan")["asset_type"] == "module"
    assert any(step["name"] == "generate_canonical_assets" for step in result.steps)
    assert any(step["name"] == "stage_asset_set_yaml" for step in result.steps)
    assert any(step["name"] == "persist_catalog" for step in result.steps)
    assert next(i for i, step in enumerate(result.steps) if step["name"] == "persist_catalog") < next(
        i for i, step in enumerate(result.steps) if step["name"] == "stage_asset_set_yaml"
    )
    assert next(i for i, step in enumerate(result.steps) if step["name"] == "persist_catalog") < next(
        i for i, step in enumerate(result.steps) if step["name"] == "persist_knowledge"
    )


def test_ingestion_orchestrator_persists_catalog_even_if_kb_projection_fails(tmp_path: Path, monkeypatch):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "domain.txt").write_text("Refinanciacion de prestamo", encoding="utf-8")
    payload = valid_payload()
    payload["domain"] = [{"domain_id": "lending", "name": "Lending", "purpose": "Loan products"}]

    monkeypatch.setattr(
        ingestion_orchestrator.IngestionOrchestratorService,
        "_optional_import",
        lambda self, module_name, friendly_name: fake_graph_module(),
    )

    class FailingKnowledgeBaseService:
        def __init__(self):
            self.repository = type("Repo", (), {"initialize": self._fail})()

        def _fail(self, **kwargs):
            raise RuntimeError("boom")

        def ingest(self, records, *, clear=False):
            raise RuntimeError("boom")

    registry = EnterpriseAssetRegistry(AssetRegistryLoader().load_file(REGISTRY_PATH))
    catalog = AssetCatalogStore(tmp_path / "catalog.sqlite")
    orchestrator = ingestion_orchestrator.IngestionOrchestratorService(
        CorpusFlowLoader(FakeLLMClient(payload)),
        canonical_asset_pipeline=CanonicalAssetPipeline(
            registry=registry,
            relation_pattern_path=RELATION_PATTERN_PATH,
            ontology_path=ONTOLOGY_PATH,
        ),
    )

    result = orchestrator.run(
        IngestionOrchestratorConfig(
            raw_path=raw_dir,
            audit_directory=tmp_path / "audit",
            asset_catalog_store=catalog,
            asset_registry=registry,
            knowledge_base_service=FailingKnowledgeBaseService(),
            extraction_instruction_mode="none",
            apply=True,
        )
    )

    assert result.catalog_assets_persisted > 0
    assert result.knowledge_base_error == "boom"
    assert catalog.get_asset("domain.lending")["asset_type"] == "domain"
    assert any(step["name"] == "persist_catalog" for step in result.steps)


def test_role_based_build_extraction_instructions_defines_all_agent_roles():
    assert [spec.name for spec in INGESTION_AGENT_SPECS] == [
        "CorpusReaderAgent",
        "FlowDesignerAgent",
        "TaskDecomposerAgent",
        "ActionExtractorAgent",
        "ConceptAgent",
        "ValidatorAgent",
    ]


def test_corpus_flow_loader_accepts_backend_like_user_task_names():
    payload = valid_payload()
    payload["user_tasks"][0]["user_task_id"] = "loan.conditions.calculate"
    payload["user_tasks"][0]["task"] = "loan.conditions.calculate"
    payload["flows"][0]["user_task_refs"] = ["loan.conditions.calculate"]

    loader = CorpusFlowLoader(FakeLLMClient(payload))

    result = loader.normalize_and_validate(payload, source_paths=["data/raw/domain.txt"])

    assert result["user_tasks"][0]["user_task_id"] == "loan_conditions_calculate"
    assert result["flows"][0]["user_task_refs"] == ["loan_conditions_calculate"]


def test_corpus_flow_loader_rejects_deprecated_user_task_fields():
    payload = valid_payload()
    payload["user_tasks"][0]["interaction_steps"] = [{"step_id": "legacy.step", "type": "user_action"}]

    loader = CorpusFlowLoader(FakeLLMClient(payload))

    with pytest.raises(FlowExtractionError, match="deprecated fields"):
        loader.normalize_and_validate(payload, source_paths=["data/raw/domain.txt"])


def test_corpus_flow_loader_accepts_html_corpus_files(tmp_path: Path):
    html_file = tmp_path / "intranet.html"
    html_file.write_text("<html><body><h1>Transfer process</h1></body></html>", encoding="utf-8")

    documents = CorpusFlowLoader(FakeLLMClient(valid_payload())).load_corpus(tmp_path)

    assert [document.path for document in documents] == [html_file]
    assert "Transfer process" in documents[0].text
