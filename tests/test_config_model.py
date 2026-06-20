from app.config.model import (
    asset_extraction_prompt,
    flow_extraction_prompt,
    load_asset_payload_composition,
    load_node_policy,
)
from app.orchestrator.node_policy import ExecutionNodePolicy


def test_flow_extraction_prompt_includes_configured_user_tasks_and_flows():
    prompt = flow_extraction_prompt()
    assert "user_tasks" in prompt
    assert "flows" in prompt
    assert "asset_set" in prompt
    assert "business_rule" in prompt
    assert "flow_id" in prompt
    assert "purpose" in prompt
    assert "user_actions" in prompt
    assert "Asset contracts:" in prompt
    assert "derived_relations" in prompt
    assert "lifecycle_states" in prompt
    assert "required_fields: flow_id, flow_name, purpose, business_event" in prompt
    assert "answers_intent" not in prompt
    assert "Business process name" not in prompt
    assert "Human readable name" not in prompt
    assert '"confidence"' not in prompt
    assert '"utterances"' not in prompt
    assert '"capabilities"' not in prompt
    assert '"concepts"' not in prompt


def test_asset_extraction_prompt_includes_configured_asset_types():
    prompt = asset_extraction_prompt()
    assert "domain" in prompt
    assert "module" in prompt
    assert "asset_set" in prompt
    assert "belongs_to_domain" in prompt
    assert "belongs_to_module" in prompt
    assert "entity" in prompt
    assert "business_rule" in prompt
    assert "qa" in prompt
    assert "causality" in prompt
    assert "when" in prompt
    assert "business_event" in prompt
    assert "Entity name" not in prompt
    assert "Rule name" not in prompt


def test_asset_payload_composition_loads_from_contracts():
    composition = load_asset_payload_composition()
    assert composition["domain"][:3] == ["domain_id", "name", "purpose"]
    assert "domain_id" in composition["module"]
    assert "members" in composition["asset_set"]
    assert "operation" in composition["tool"]
    assert "path" in composition["document"]
    assert "settings" in composition["configuration"]
    assert "relations" in composition["entity"]
    assert "rules" in composition["ruleset"]
    assert "aliases" in composition["concept"]
    assert composition["flow"][:4] == ["flow_id", "flow_name", "purpose", "business_event"]
    assert "execution_nodes" in composition["process"]
    assert "when" in composition["business_rule"]


def test_node_policy_loads_allowed_types_from_config():
    policy = ExecutionNodePolicy()
    allowed_process = policy.allowed_types.get("process")
    assert allowed_process is not None
    assert "user_task" in allowed_process
    assert "service_call" in allowed_process
    assert "notification" in allowed_process


def test_load_node_policy_returns_sets():
    allowed = load_node_policy()
    assert isinstance(allowed, dict)
    assert "flow" in allowed
    assert isinstance(allowed["flow"], set)
