from typer.testing import CliRunner
from types import SimpleNamespace
import json
import sqlite3

from app.cli import app
from app.api import _catalog_asset_tree
from app.platform_cli import app as kb_app
from app.knowledge_base.catalog_store import AssetCatalogStore


def test_ask_suite_command_is_registered():
    result = CliRunner().invoke(app, ["ask-suite", "--help"])

    assert result.exit_code == 0
    assert "Run end-to-end ask scenarios" in result.output
    assert "--scenario-file" in result.output


def test_kb_commands_are_registered():
    for command in ["kb", "kb-views", "kb-route", "kb-show", "kb-query", "kb-search", "kb-evidence"]:
        result = CliRunner().invoke(app, [command, "--help"])

        assert result.exit_code == 0


def test_orchestrator_definition_validation_command_is_registered():
    result = CliRunner().invoke(app, ["orchestrator-validate-definitions", "--help"])

    assert result.exit_code == 0
    assert "Validate flow/process YAML definitions" in result.output


def test_direct_kb_commands_are_registered():
    result = CliRunner().invoke(kb_app, ["--help"])

    assert result.exit_code == 0
    assert "start" in result.output
    assert "ingest" in result.output
    assert "query" in result.output
    assert "reset-ingest" in result.output
    assert "query-catalog" not in result.output
    assert "query-evidence" not in result.output
    assert "query-engine" not in result.output
    assert "│ show" not in result.output
    assert "│ search" not in result.output


def test_kb_reset_ingest_has_all_databases_option():
    result = CliRunner().invoke(kb_app, ["reset-ingest", "--help"])

    assert result.exit_code == 0
    assert "--all-databases" in result.output


def test_kb_query_metadata_flag_is_registered():
    result = CliRunner().invoke(kb_app, ["query", "--help"])

    assert result.exit_code == 0
    assert "--metadata" in result.output


def test_kb_query_metadata_tree_mode_runs_with_empty_catalog(tmp_path, monkeypatch):
    processed_directory = tmp_path / "processed"
    catalog_path = processed_directory / "knowledge_base" / "asset_catalog.sqlite"
    AssetCatalogStore(catalog_path).initialize()

    monkeypatch.setattr("app.cli.load_settings", lambda: SimpleNamespace(processed_directory=processed_directory))

    result = CliRunner().invoke(app, ["kb", "--metadata", "--format", "tree"])

    assert result.exit_code == 0
    assert "catalog_metadata" in result.output
    assert "asset_contracts" in result.output


def test_kb_query_metadata_tree_shows_flow_task_action_tool_hierarchy(tmp_path, monkeypatch):
    processed_directory = tmp_path / "processed"
    catalog_path = processed_directory / "knowledge_base" / "asset_catalog.sqlite"
    store = AssetCatalogStore(catalog_path)
    store.initialize()

    with sqlite3.connect(catalog_path) as connection:
        connection.execute(
            """
            INSERT INTO assets (
                asset_id, asset_type, name, version, status, primary_kb, stores_json, payload_json,
                canonical_name, normalized_name, aliases_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "flow.loan.refinance",
                "flow",
                "Refinanciamiento",
                "1.0.0",
                "approved",
                "process_kb",
                json.dumps(["repository", "graph", "vector"]),
                json.dumps(
                    {
                        "flow_id": "flow.loan.refinance",
                        "flow_name": "Refinanciamiento",
                        "purpose": "Refinanciar",
                        "business_event": "loan.refinance.requested",
                        "user_tasks": [
                            {
                                "user_task_id": "user_task.loan.refinance.identify",
                                "task": "identify eligible loan",
                                "type": "user_task",
                                "name": "Identify eligible loan",
                                "description": "Identify eligible loan",
                                "user_actions": [
                                    {
                                        "action_id": "action.loan.refinance.identify",
                                        "type": "back",
                                        "implementation_type": "tool_call",
                                        "lifecycle_state": "on_user_enter",
                                        "tool_ids": ["tool.loan.conditions.calculate"],
                                    }
                                ],
                                "tools": [
                                    {
                                        "tool_id": "tool.loan.conditions.calculate",
                                        "tool_type": "backend_tool",
                                        "operation": "calculate",
                                        "resource": "loan.conditions",
                                    }
                                ],
                            }
                        ],
                    }
                ),
                "Refinanciamiento",
                "refinanciamiento",
                json.dumps([]),
            ),
        )
        connection.execute(
            """
            INSERT INTO assets (
                asset_id, asset_type, name, version, status, primary_kb, stores_json, payload_json,
                canonical_name, normalized_name, aliases_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "user_task.loan.refinance.identify",
                "user_task",
                "Identify eligible loan",
                "1.0.0",
                "approved",
                "business_model_kb",
                json.dumps(["repository", "graph"]),
                json.dumps(
                    {
                        "user_task_id": "user_task.loan.refinance.identify",
                        "task": "identify eligible loan",
                        "type": "user_task",
                        "name": "Identify eligible loan",
                        "description": "Identify eligible loan",
                        "user_actions": [
                            {
                                "action_id": "action.loan.refinance.identify",
                                "type": "back",
                                "implementation_type": "tool_call",
                                "lifecycle_state": "on_user_enter",
                                "tool_ids": ["tool.loan.conditions.calculate"],
                            }
                        ],
                        "tools": [
                            {
                                "tool_id": "tool.loan.conditions.calculate",
                                "tool_type": "backend_tool",
                                "operation": "calculate",
                                "resource": "loan.conditions",
                            }
                        ],
                    }
                ),
                "Identify eligible loan",
                "identify eligible loan",
                json.dumps([]),
            ),
        )
        connection.execute(
            """
            INSERT INTO assets (
                asset_id, asset_type, name, version, status, primary_kb, stores_json, payload_json,
                canonical_name, normalized_name, aliases_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "tool.loan.conditions.calculate",
                "tool",
                "Calculate loan conditions",
                "1.0.0",
                "approved",
                "business_model_kb",
                json.dumps(["repository", "graph"]),
                json.dumps(
                    {
                        "tool_id": "tool.loan.conditions.calculate",
                        "tool_type": "backend_tool",
                        "operation": "calculate",
                        "resource": "loan.conditions",
                    }
                ),
                "Calculate loan conditions",
                "calculate loan conditions",
                json.dumps([]),
            ),
        )
        connection.execute(
            "INSERT INTO relationships (source_asset_id, relation_type, target_asset_id, metadata_json) VALUES (?, ?, ?, ?)",
            ("flow.loan.refinance", "decomposes_to_user_task", "user_task.loan.refinance.identify", "{}"),
        )
        connection.execute(
            "INSERT INTO relationships (source_asset_id, relation_type, target_asset_id, metadata_json) VALUES (?, ?, ?, ?)",
            ("user_task.loan.refinance.identify", "invokes_tool", "tool.loan.conditions.calculate", "{}"),
        )
        connection.commit()

    monkeypatch.setattr("app.cli.load_settings", lambda: SimpleNamespace(processed_directory=processed_directory))

    result = CliRunner().invoke(app, ["kb", "--metadata", "--format", "tree"])

    assert result.exit_code == 0
    assert "asset_hierarchy" in result.output
    assert "flow.loan.refinance" in result.output


def test_kb_query_tree_defaults_to_all_statuses_and_resolves_flow_children(tmp_path, monkeypatch):
    processed_directory = tmp_path / "processed"
    catalog_path = processed_directory / "knowledge_base" / "asset_catalog.sqlite"
    store = AssetCatalogStore(catalog_path)
    store.initialize()

    with sqlite3.connect(catalog_path) as connection:
        connection.execute(
            """
            INSERT INTO assets (
                asset_id, asset_type, name, version, status, primary_kb, stores_json, payload_json,
                canonical_name, normalized_name, aliases_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "flow.loan.refinance",
                "flow",
                "Refinanciamiento",
                "1.0.0",
                "draft",
                "process_kb",
                json.dumps(["repository", "graph", "vector"]),
                json.dumps(
                    {
                        "flow_id": "flow.loan.refinance",
                        "flow_name": "Refinanciamiento",
                        "purpose": "Refinanciar",
                        "business_event": "loan.refinance.requested",
                        "user_tasks": [
                            {
                                "user_task_id": "user_task.loan.refinance.identify",
                                "task": "identify eligible loan",
                                "type": "user_task",
                                "name": "Identify eligible loan",
                                "description": "Identify eligible loan",
                                "user_actions": [
                                    {
                                        "action_id": "action.loan.refinance.identify",
                                        "type": "back",
                                        "implementation_type": "tool_call",
                                        "lifecycle_state": "on_user_enter",
                                        "tool_ids": ["tool.loan.conditions.calculate"],
                                    }
                                ],
                                "tools": [
                                    {
                                        "tool_id": "tool.loan.conditions.calculate",
                                        "tool_type": "backend_tool",
                                        "operation": "calculate",
                                        "resource": "loan.conditions",
                                    }
                                ],
                            }
                        ],
                    }
                ),
                "Refinanciamiento",
                "refinanciamiento",
                json.dumps([]),
            ),
        )
        connection.execute(
            """
            INSERT INTO assets (
                asset_id, asset_type, name, version, status, primary_kb, stores_json, payload_json,
                canonical_name, normalized_name, aliases_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "user_task.loan.refinance.identify",
                "user_task",
                "Identify eligible loan",
                "1.0.0",
                "draft",
                "business_model_kb",
                json.dumps(["repository", "graph"]),
                json.dumps(
                    {
                        "user_task_id": "user_task.loan.refinance.identify",
                        "task": "identify eligible loan",
                        "type": "user_task",
                        "name": "Identify eligible loan",
                        "description": "Identify eligible loan",
                        "user_actions": [
                            {
                                "action_id": "action.loan.refinance.identify",
                                "type": "back",
                                "implementation_type": "tool_call",
                                "lifecycle_state": "on_user_enter",
                                "tool_ids": ["tool.loan.conditions.calculate"],
                            }
                        ],
                        "tools": [
                            {
                                "tool_id": "tool.loan.conditions.calculate",
                                "tool_type": "backend_tool",
                                "operation": "calculate",
                                "resource": "loan.conditions",
                            }
                        ],
                    }
                ),
                "Identify eligible loan",
                "identify eligible loan",
                json.dumps([]),
            ),
        )
        connection.execute(
            """
            INSERT INTO assets (
                asset_id, asset_type, name, version, status, primary_kb, stores_json, payload_json,
                canonical_name, normalized_name, aliases_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "tool.loan.conditions.calculate",
                "tool",
                "Calculate loan conditions",
                "1.0.0",
                "draft",
                "business_model_kb",
                json.dumps(["repository", "graph"]),
                json.dumps(
                    {
                        "tool_id": "tool.loan.conditions.calculate",
                        "tool_type": "backend_tool",
                        "operation": "calculate",
                        "resource": "loan.conditions",
                    }
                ),
                "Calculate loan conditions",
                "calculate loan conditions",
                json.dumps([]),
            ),
        )
        connection.execute(
            "INSERT INTO relationships (source_asset_id, relation_type, target_asset_id, metadata_json) VALUES (?, ?, ?, ?)",
            ("flow.loan.refinance", "decomposes_to_user_task", "user_task.loan.refinance.identify", "{}"),
        )
        connection.execute(
            "INSERT INTO relationships (source_asset_id, relation_type, target_asset_id, metadata_json) VALUES (?, ?, ?, ?)",
            ("user_task.loan.refinance.identify", "invokes_tool", "tool.loan.conditions.calculate", "{}"),
        )
        connection.commit()

    monkeypatch.setattr("app.cli.load_settings", lambda: SimpleNamespace(processed_directory=processed_directory))

    result = CliRunner().invoke(kb_app, ["query", "--asset-type", "flow", "--tree", "--format", "tree"])

    assert result.exit_code == 0
    assert "flow.loan.refinance" in result.output
    assert "user_task.loan.refinance.identify" in result.output
    assert "tool.loan.conditions.calculate" in result.output


def test_catalog_asset_tree_prioritizes_review_before_active():
    tree = _catalog_asset_tree(
        [
            {
                "asset_id": "flow.loan.active",
                "asset_type": "flow",
                "name": "Active Flow",
                "version": "1.0.0",
                "status": "active",
                "stores": ["graph"],
                "asset_set_id": "loan-set",
            },
            {
                "asset_id": "flow.loan.review",
                "asset_type": "flow",
                "name": "Review Flow",
                "version": "1.0.0",
                "status": "ready_for_review",
                "stores": ["graph"],
                "asset_set_id": "loan-set",
            },
        ]
    )

    assert tree[0]["label"] == "Catalog"
    children = tree[0]["children"][0]["children"]
    assert [item["status"] for item in children] == ["ready_for_review", "active"]
