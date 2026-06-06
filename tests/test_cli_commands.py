from typer.testing import CliRunner

from app.cli import app
from app.platform_cli import app as kb_app


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
