from pathlib import Path

from app.agents.ask import AskCoordinatorAgent
from app.agents.ask import KnowledgeRouterAgent
from app.agents.catalog import build_agent_registry, build_asset_specialist_agents
from app.agents.catalog_loader import AgentCatalogLoader
from app.agents.generic import build_agent_from_definition
from app.agents.skills.loader import SkillCatalogLoader
from app.agents.ingestion import IngestionCoordinatorAgent
from app.config.settings import load_settings
from app.ingestion.orchestrator import IngestionOrchestrationResult, IngestionOrchestratorConfig


class FakeAskService:
    def resolve(self, question, trace=None):
        if trace:
            trace("fake", "resolved")
        return {"question": question, "answer": "ok"}


class FakeIngestionOrchestrator:
    def run(self, config):
        return IngestionOrchestrationResult(
            mode="preview",
            audit_path=config.audit_directory / "audit.json",
            source_files=[str(config.raw_path)],
            flows_persisted=0,
            user_tasks_extracted=1,
            tools_extracted=1,
            steps=[{"step": "fake"}],
        )


def test_asset_specialist_agents_are_registered():
    registry = build_agent_registry()

    agent_ids = {agent.definition.agent_id for agent in registry.list_agents()}

    assert {
        "agent.system.planning",
        "agent.system.delegator",
        "agent.system.monitoring",
        "agent.business.loan.executive",
        "agent.business.platform.admin",
        "agent.asset.flow",
        "agent.asset.process",
        "agent.asset.rule",
        "agent.asset.qa",
        "agent.asset.entity",
        "agent.asset.tool",
        "agent.asset.configuration",
        "agent.ask.knowledge_router",
    }.issubset(agent_ids)


def test_agent_catalog_loader_builds_configured_agents():
    settings = load_settings()
    definitions = AgentCatalogLoader().load_file(settings.agent_catalog_path)

    agent_ids = {definition.agent_id for definition in definitions}
    loan_agent = next(definition for definition in definitions if definition.agent_id == "agent.business.loan.executive")

    assert {"agent.system.planning", "agent.system.delegator", "agent.system.monitoring"}.issubset(agent_ids)
    assert loan_agent.agent_class == "worker"
    assert loan_agent.skill_ids == ["loan-origination-review"]
    assert loan_agent.tool_ids == [
        "tool.loan.application.lookup",
        "tool.loan.risk.summary",
    ]


def test_skill_catalog_loader_reads_markdown_skills():
    settings = load_settings()
    skills = SkillCatalogLoader().load_index(settings.agent_skills_path)

    loan_skill = skills["loan-origination-review"]

    assert loan_skill.name == "loan-origination-review"
    assert "loan-originations" in loan_skill.description.lower()
    assert "Use this skill for loan operations review" in loan_skill.instructions


def test_configured_business_agent_enforces_tool_policy():
    settings = load_settings()
    definitions = AgentCatalogLoader().load_file(settings.agent_catalog_path)
    loan_agent = build_agent_from_definition(
        next(definition for definition in definitions if definition.agent_id == "agent.business.loan.executive")
    )

    allowed_result = loan_agent.run({"tool_ids": ["tool.loan.application.lookup"]})
    denied_result = loan_agent.run({"tool_ids": ["tool.loan.application.lookup", "tool.forbidden.extra"]})

    assert allowed_result.status == "ok"
    assert allowed_result.output["decision"] == "assist"
    assert [event["node"] for event in allowed_result.trace] == ["initialize", "load_skills", "validate_policy", "route_class", "finalize"]
    assert allowed_result.output["loaded_skills"][0]["skill_id"] == "loan-origination-review"
    assert denied_result.status == "failed"
    assert "tool.forbidden.extra" in (denied_result.error or "")


def test_ask_coordinator_wraps_ask_service():
    agent = AskCoordinatorAgent(FakeAskService())

    result = agent.run("Como refinancio mi prestamo?")

    assert result.status == "ok"
    assert result.agent_id == "agent.ask.coordinator"
    assert result.output["answer"] == "ok"
    assert result.trace == [{"step": "fake", "detail": "resolved"}]


def test_ingestion_coordinator_wraps_orchestrator(tmp_path: Path):
    agent = IngestionCoordinatorAgent(FakeIngestionOrchestrator())
    config = IngestionOrchestratorConfig(
        raw_path=tmp_path / "raw",
        audit_directory=tmp_path / "audit",
    )

    result = agent.run(config)

    assert result.status == "ok"
    assert result.agent_id == "agent.ingestion.coordinator"
    assert result.output.user_tasks_extracted == 1
    assert result.trace[0]["graph"] == "ingestion_orchestrator"


def test_asset_specialist_run_returns_registered_decision():
    agent = build_asset_specialist_agents()[0]

    result = agent.run({"candidate": "loan.refinance"})

    assert result.status == "ok"
    assert result.output["decision"] == "specialist_registered"


def test_knowledge_router_agent_can_route_to_multiple_sources():
    agent = KnowledgeRouterAgent()

    result = agent.run(
        {
            "question": "Como se aplica la regla de pago automatico en el proceso?",
            "search_terms": ["pago", "automatico", "proceso"],
            "question_understanding": {
                "routing_hints": {
                    "needs_answer": True,
                    "needs_process": True,
                }
            },
            "asset_search": {
                "enabled": True,
                "primary_assets": ["qa.automatic_payment_account_required"],
                "supporting_assets": ["business_rule.automatic_payment_account_required"],
            },
        }
    )

    sources = {route["source"] for route in result.output}

    assert result.status == "ok"
    assert {"qa", "process_flows", "rules_policies", "entities"}.issubset(sources)
