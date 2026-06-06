from __future__ import annotations

from app.approval.policy import AlwaysHumanApprovalPolicy
from app.approval.service import ApprovalService
from app.knowledge_base.loader import AssetRegistryLoader
from app.knowledge_base.catalog_store import AssetCatalogStore
from app.knowledge_base.asset_sets import AssetSetDeploymentService
from app.knowledge_base.registry import EnterpriseAssetRegistry
from app.knowledge_base.repository import EnterpriseAssetRepository
from app.knowledge_base.models import EnterpriseAsset
from app.knowledge_base.search import AssetSearchService
from app.knowledge_base.sync import AssetSyncService
from app.knowledge_base.validation import AssetValidationService
from app.audit.noop import NoopAuditSink
from app.audit.service import AuditService
from app.capability.registry import RegistryCapabilityProvider
from app.capability.service import CapabilityService
from app.config.settings import load_settings
from app.ask.ai import LLMFlowSelectionProvider
from app.ask.answer import AnswerBuilder
from app.ask.intent import FlowSelectionService
from app.ask.service import AskService
from app.ask.understanding import LLMQuestionUnderstandingProvider, QuestionUnderstandingService
from app.agents.ask import AskCoordinatorAgent
from app.agents.catalog import build_agent_registry as build_default_agent_registry
from app.agents.registry import AgentRegistry
from app.ingestion.llm_flow_loader import CorpusFlowLoader, OpenAICompatibleLLMClient
from app.ingestion.orchestrator import IngestionOrchestratorService
from app.knowledge_base.adapters.graph.neo4j import Neo4jKnowledgeBaseGraphAdapter
from app.knowledge_base.adapters.document import SQLiteDocumentKnowledgeBaseAdapter
from app.knowledge_base.adapters.vector import QdrantKnowledgeBaseVectorAdapter
from app.knowledge_base.service import KnowledgeBaseService
from app.launcher.runtime import LauncherRuntimeService
from app.orchestrator.assets import OrchestratorAssetRegistry
from app.orchestrator.repository import Neo4jOrchestratorRepository
from app.orchestrator.service import OrchestratorService
from app.orchestrator.orchestration_executor import OrchestrationExecutorService
from app.planning.service import PlanningService


def build_agent_registry() -> AgentRegistry:
    return build_default_agent_registry()


def build_ask_coordinator_agent() -> AskCoordinatorAgent:
    return AskCoordinatorAgent(build_ask_service())


def build_graph_repository() -> Neo4jKnowledgeBaseGraphAdapter:
    settings = load_settings()
    return Neo4jKnowledgeBaseGraphAdapter(
        neo4j_uri=settings.neo4j_uri,
        neo4j_user=settings.neo4j_user,
        neo4j_password=settings.neo4j_password,
    )


def build_ingestion_orchestrator() -> IngestionOrchestratorService:
    settings = load_settings()
    return IngestionOrchestratorService(
        CorpusFlowLoader(
            OpenAICompatibleLLMClient(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
                model=settings.intent_llm_model,
            )
        )
    )


def build_orchestration_executor_service(orchestrator_service: OrchestratorService | None = None) -> OrchestrationExecutorService:
    return OrchestrationExecutorService(
        orchestrator_service=orchestrator_service or build_orchestrator_service(),
        asset_repository=build_enterprise_asset_repository(),
        knowledge_base_service=build_knowledge_base_service(),
    )


def build_process_execution_service(orchestrator_service: OrchestratorService | None = None) -> OrchestrationExecutorService:
    """Backward-compatible alias. Prefer build_orchestration_executor_service."""
    return build_orchestration_executor_service(orchestrator_service)


def build_orchestrator_service() -> OrchestratorService:
    graph = build_graph_repository()
    repository = Neo4jOrchestratorRepository(graph.driver)
    repository.initialize()
    return OrchestratorService(repository=repository)


def build_orchestrator_asset_registry() -> OrchestratorAssetRegistry:
    return OrchestratorAssetRegistry(
        knowledge_base_service=build_knowledge_base_service(),
        asset_repository=build_enterprise_asset_repository(),
    )


def build_enterprise_asset_registry() -> EnterpriseAssetRegistry:
    settings = load_settings()
    config = AssetRegistryLoader().load_file(settings.asset_registry_path)
    return EnterpriseAssetRegistry(config)


def build_enterprise_asset_repository() -> EnterpriseAssetRepository:
    graph_repository = build_graph_repository()
    try:
        graph_assets = graph_repository.list_assets(approved_only=False)
    finally:
        graph_repository.close()
    return EnterpriseAssetRepository(graph_assets)


def build_asset_catalog_store() -> AssetCatalogStore:
    settings = load_settings()
    store = AssetCatalogStore(settings.asset_catalog_path)
    store.initialize(clear=False)
    return store


def build_asset_set_deployment_service() -> AssetSetDeploymentService:
    settings = load_settings()
    return AssetSetDeploymentService(
        store=build_asset_catalog_store(),
        registry=build_enterprise_asset_registry(),
        graph=build_graph_repository(),
        vector=QdrantKnowledgeBaseVectorAdapter(
            settings.qdrant_host,
            settings.qdrant_api_key,
        ),
        document=SQLiteDocumentKnowledgeBaseAdapter(
            settings.processed_directory / "knowledge_base" / "document_kb.sqlite"
        ),
    )


def build_launcher_runtime_service() -> LauncherRuntimeService:
    return LauncherRuntimeService(build_asset_catalog_store())


def build_asset_search_service() -> AssetSearchService:
    return AssetSearchService(
        registry=build_enterprise_asset_registry(),
        repository=build_unified_catalog_repository(),
    )


def build_unified_catalog_repository() -> EnterpriseAssetRepository:
    """Build the governed Ask asset view from active sets and approved legacy assets."""
    store = build_asset_catalog_store()
    values: dict[str, EnterpriseAsset] = {}
    legacy_repository = EnterpriseAssetRepository.from_catalog_store(store)
    for row in store.list_assets(status="approved", limit=10_000):
        asset = legacy_repository.get(row["asset_id"])
        if asset is not None:
            values[asset.asset_id] = asset
    for row in store.list_active_assets(environment="dev"):
        payload = row.get("payload") or {}
        asset = EnterpriseAsset.model_validate(payload).model_copy(update={"status": "active"})
        values[asset.asset_id] = asset
    return EnterpriseAssetRepository(list(values.values()))


def build_asset_validation_service() -> AssetValidationService:
    return AssetValidationService(
        registry=build_enterprise_asset_registry(),
        repository=build_enterprise_asset_repository(),
    )


def build_asset_sync_service() -> AssetSyncService:
    settings = load_settings()
    return AssetSyncService(
        repository=build_enterprise_asset_repository(),
        output_directory=settings.processed_directory / "asset_index",
    )


def build_knowledge_base_service() -> KnowledgeBaseService:
    return KnowledgeBaseService(build_graph_repository())


def build_ask_service() -> AskService:
    settings = load_settings()
    if not settings.use_ai_providers:
        raise RuntimeError(
            "USE_AI_PROVIDERS must be true. The ask flow requires an LLM and the Neo4j knowledge base graph adapter."
        )

    graph_repository = build_graph_repository()
    startup_records = graph_repository.list_all_records()
    capability_service = CapabilityService(RegistryCapabilityProvider(startup_records))
    answer_builder = AnswerBuilder()
    approval_service = ApprovalService(AlwaysHumanApprovalPolicy())
    audit_service = AuditService(NoopAuditSink())

    try:
        return AskService(
            knowledge_base_service=KnowledgeBaseService(
                graph_repository
            ),
            question_understanding_service=QuestionUnderstandingService(
                LLMQuestionUnderstandingProvider(
                    api_key=settings.openai_api_key,
                    base_url=settings.openai_base_url,
                    model=settings.intent_llm_model,
                )
            ),
            flow_selection_service=FlowSelectionService(
                LLMFlowSelectionProvider(
                    openai_api_key=settings.openai_api_key,
                    base_url=settings.openai_base_url,
                    model=settings.intent_llm_model,
                )
            ),
            capability_service=capability_service,
            answer_builder=answer_builder,
            approval_service=approval_service,
            audit_service=audit_service,
            planning_service=PlanningService(),
            asset_search_service=build_asset_search_service(),
            trace_directory=settings.processed_directory / "ask_trace",
        )
    except RuntimeError as exc:
        raise RuntimeError(f"Could not start required knowledge base/LLM providers: {exc}") from exc
