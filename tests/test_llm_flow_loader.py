import base64
import zipfile
from pathlib import Path

import pytest

from app.ingestion.llm_flow_loader import CorpusFlowLoader, FlowExtractionError
from app.ingestion.pipeline import IngestionPipelineConfig, IngestionPipelineService
from app.ingestion import pipeline as ingestion_pipeline
from app.knowledge_graph.vocabulary import ConceptVocabulary
from app.ingestion.reasoning import (
    AutoGenIngestionReasoningProvider,
    INGESTION_AGENT_SPECS,
    IngestionReasoningService,
    RoleBasedIngestionReasoningProvider,
)


class FakeLLMClient:
    def __init__(self, payload):
        self.payload = payload

    def complete_json(self, system_prompt: str, user_content):
        assert "Technical CRUD" in system_prompt
        assert isinstance(user_content, list)
        assert any(item.get("type") == "text" for item in user_content)
        return self.payload


def valid_payload():
    return {
        "user_tasks": [
            {
                "user_task_id": "review_refinance_options",
                "task": "review_refinance_options",
                "type": "user_task",
                "name": "Review Refinance Options",
                "description": "Review refinance choices with the customer.",
                "front_actions": [
                    {
                        "action": "ui.refinance.calculate",
                        "operation": "calculate",
                        "resource": "loan_refinance",
                        "label": "Calculate refinance",
                        "triggers": "loan_refinance.calculate",
                    }
                ],
                "back_actions": [
                    {
                        "action": "loan.conditions.calculate",
                        "operation": "calculate",
                        "resource": "loan",
                        "description": "Calculate new loan conditions.",
                    }
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
    assert result["user_tasks"][0]["back_actions"][0]["action"] == "loan.conditions.calculate"
    assert result["action_registry"] == [
        {
            "action": "loan.conditions.calculate",
            "type": "back_action",
            "operation": "calculate",
            "resource": "loan",
            "label": None,
            "triggers": None,
            "description": "Calculate new loan conditions.",
            "user_tasks": ["review_refinance_options"],
            "flows": ["loan.refinance"],
        },
        {
            "action": "ui.refinance.calculate",
            "type": "front_action",
            "operation": "calculate",
            "resource": "loan_refinance",
            "label": "Calculate refinance",
            "triggers": "loan_refinance.calculate",
            "description": None,
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


def test_corpus_flow_loader_adds_ingestion_reasoning_context(tmp_path: Path):
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
        reasoning_service=IngestionReasoningService(RoleBasedIngestionReasoningProvider()),
    )
    result = loader.extract(raw_dir)

    assert result["flows"][0]["flow_id"] == "loan.refinance"


def test_ingestion_pipeline_writes_artifacts_and_audit(tmp_path: Path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "domain.txt").write_text("Refinanciacion de prestamo", encoding="utf-8")

    pipeline = IngestionPipelineService(CorpusFlowLoader(FakeLLMClient(valid_payload())))
    result = pipeline.run(
        IngestionPipelineConfig(
            raw_path=raw_dir,
            flow_directory=tmp_path / "generated" / "flows",
            user_task_directory=tmp_path / "generated" / "user_tasks",
            action_registry_directory=tmp_path / "generated" / "action_registry",
            audit_directory=tmp_path / "audit",
            reasoning_mode="none",
        )
    )

    assert result.mode == "preview"
    assert result.flows_written == 1
    assert (tmp_path / "generated" / "flows" / "loan_refinance.flow.json").exists()
    assert result.audit_path.exists()
    audit_text = result.audit_path.read_text(encoding="utf-8")
    assert "scan_and_parse_corpus" in audit_text
    assert "write_audit" in audit_text


def test_langgraph_ingestion_pipeline_runs_nodes_with_graph_orchestrator(tmp_path: Path, monkeypatch):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "domain.txt").write_text("Refinanciacion de prestamo", encoding="utf-8")

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

    monkeypatch.setattr(
        ingestion_pipeline.LangGraphIngestionPipelineService,
        "_optional_import",
        lambda self, module_name, friendly_name: FakeGraphModule,
    )

    pipeline = ingestion_pipeline.LangGraphIngestionPipelineService(
        CorpusFlowLoader(FakeLLMClient(valid_payload()))
    )
    result = pipeline.run(
        IngestionPipelineConfig(
            raw_path=raw_dir,
            flow_directory=tmp_path / "generated" / "flows",
            user_task_directory=tmp_path / "generated" / "user_tasks",
            action_registry_directory=tmp_path / "generated" / "action_registry",
            audit_directory=tmp_path / "audit",
            reasoning_mode="none",
            max_validation_retries=1,
            require_human_review=True,
        )
    )

    assert result.flows_written == 1
    assert any(step["owner"] == "custom_langgraph" for step in result.steps)
    assert "requires_human_review" in result.audit_path.read_text(encoding="utf-8")


def test_autogen_ingestion_reasoning_defines_all_agent_roles():
    assert [spec.name for spec in INGESTION_AGENT_SPECS] == [
        "CorpusReaderAgent",
        "FlowDesignerAgent",
        "TaskDecomposerAgent",
        "ActionExtractorAgent",
        "ConceptAgent",
        "ValidatorAgent",
    ]


def test_autogen_ingestion_reasoning_parses_agent_findings():
    provider = AutoGenIngestionReasoningProvider(api_key="test-key")

    class Message:
        def __init__(self, source: str, content: str):
            self.source = source
            self.content = content

    result = provider._result_from_messages(
        [
            Message("user", "ignore"),
            Message("CorpusReaderAgent", "FINDING: customer asks for loan refinance"),
            Message("ValidatorAgent", "- FINDING: reject backend operation as user_task"),
        ]
    )

    assert [finding.agent for finding in result.findings] == [
        "CorpusReaderAgent",
        "ValidatorAgent",
    ]
    assert result.findings[0].finding == "customer asks for loan refinance"


def test_corpus_flow_loader_rejects_backend_operation_as_user_task():
    payload = valid_payload()
    payload["user_tasks"][0]["user_task_id"] = "loan.conditions.calculate"
    payload["user_tasks"][0]["task"] = "loan.conditions.calculate"
    payload["flows"][0]["user_task_refs"] = ["loan.conditions.calculate"]

    loader = CorpusFlowLoader(FakeLLMClient(payload))

    with pytest.raises(FlowExtractionError, match="backend operation"):
        loader.normalize_and_validate(payload, source_paths=["data/raw/domain.txt"])
