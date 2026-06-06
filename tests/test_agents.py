from pathlib import Path

from app.agents.ask import AskCoordinatorAgent
from app.agents.ask import KnowledgeRouterAgent
from app.agents.catalog import build_agent_registry, build_asset_specialist_agents
from app.agents.ingestion import IngestionCoordinatorAgent
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
        "agent.asset.flow",
        "agent.asset.process",
        "agent.asset.rule",
        "agent.asset.qa",
        "agent.asset.entity",
        "agent.asset.tool",
        "agent.asset.configuration",
        "agent.ask.knowledge_router",
    }.issubset(agent_ids)


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
