import base64
import zipfile
from pathlib import Path

import pytest

from app.ingestion.llm_flow_loader import CorpusFlowLoader, FlowExtractionError
from app.ingestion.orchestrator import IngestionOrchestratorConfig, IngestionOrchestratorService
from app.ingestion import orchestrator as ingestion_orchestrator
from app.knowledge_base.vocabulary import ConceptVocabulary
from app.ingestion.orchestrator import (
    INGESTION_AGENT_SPECS,
    RoleBasedExtractionInstructionBuilder,
)


class FakeLLMClient:
    def __init__(self, payload):
        self.payload = payload

    def complete_json(self, system_prompt: str, user_content):
        assert "Technical CRUD" in system_prompt
        assert isinstance(user_content, list)
        assert any(item.get("type") == "text" for item in user_content)
        return self.payload


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
                "intent": "loan.refinance",
                "business_event": "LoanRefinancingRequested",
                "confidence": 0.9,
                "utterances": ["quiero refinanciar mi prestamo"],
                "plan": ["review_refinance_options"],
                "user_task_refs": ["review_refinance_options"],
                "capabilities": ["loan.conditions.calculate"],
                "concepts": ["Loan", "LoanRefinance"],
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
    assert result["flows"][0]["user_task_refs"] == ["review_refinance_options"]
    assert "credito" in result["flows"][0]["concept_aliases"]["Loan"]
    assert "prestamo" in result["flows"][0]["concept_aliases"]["Loan"]
    assert result["user_tasks"][0]["tools"][1]["tool_id"] == "loan.conditions.calculate"
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
    audit_text = result.audit_path.read_text(encoding="utf-8")
    assert "scan_and_parse_corpus" in audit_text
    assert "analyze_semantics_classify_corpus" in audit_text
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
    assert "requires_human_review" in result.audit_path.read_text(encoding="utf-8")


def test_role_based_build_extraction_instructions_defines_all_agent_roles():
    assert [spec.name for spec in INGESTION_AGENT_SPECS] == [
        "CorpusReaderAgent",
        "FlowDesignerAgent",
        "TaskDecomposerAgent",
        "ActionExtractorAgent",
        "ConceptAgent",
        "ValidatorAgent",
    ]


def test_corpus_flow_loader_rejects_backend_operation_as_user_task():
    payload = valid_payload()
    payload["user_tasks"][0]["user_task_id"] = "loan.conditions.calculate"
    payload["user_tasks"][0]["task"] = "loan.conditions.calculate"
    payload["flows"][0]["user_task_refs"] = ["loan.conditions.calculate"]

    loader = CorpusFlowLoader(FakeLLMClient(payload))

    with pytest.raises(FlowExtractionError, match="backend operation"):
        loader.normalize_and_validate(payload, source_paths=["data/raw/domain.txt"])


def test_corpus_flow_loader_accepts_html_corpus_files(tmp_path: Path):
    html_file = tmp_path / "intranet.html"
    html_file.write_text("<html><body><h1>Transfer process</h1></body></html>", encoding="utf-8")

    documents = CorpusFlowLoader(FakeLLMClient(valid_payload())).load_corpus(tmp_path)

    assert [document.path for document in documents] == [html_file]
    assert "Transfer process" in documents[0].text
