from app.ask.ai import OpenAIJSONClient
from app.capability.registry import RegistryCapabilityProvider
from app.tools.models import ToolDefinition
from conftest import sample_records


def test_legacy_actions_project_to_canonical_tools():
    records = sample_records("loan.refinance")
    tools = RegistryCapabilityProvider(records).list_registered_tools()

    tool_by_id = {tool.tool_id: tool for tool in tools}

    assert tool_by_id["ui.refinance.calculate"].tool_type == "frontend_tool"
    assert tool_by_id["ui.refinance.calculate"].frontend_event == "loan_refinance.calculate"
    assert tool_by_id["loan.conditions.calculate"].tool_type == "backend_tool"
    assert tool_by_id["loan.conditions.calculate"].backend_protocol is None


def test_llm_client_exposes_llm_tool_definition(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    client = OpenAIJSONClient(model="test-model")

    assert isinstance(client.tool_definition, ToolDefinition)
    assert client.tool_definition.tool_type == "llm_tool"
    assert client.tool_definition.llm_operation == "json_completion"
    assert client.tool_definition.backend_protocol is None
