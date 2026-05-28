from __future__ import annotations

from app.approval.policy import AlwaysHumanApprovalPolicy
from app.approval.service import ApprovalService
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
from app.ingestion.flow_loader import FileKnowledgeIngestionProvider, FlowKnowledgeLoader
from app.knowledge_graph.neo4j import Neo4jKnowledgeGraphRepository
from app.knowledge_graph.service import KnowledgeGraphService
from app.orchestrator.service import OrchestratorService
from app.orchestrator.process_execution import ProcessExecutionService


def build_ingestion_provider() -> FileKnowledgeIngestionProvider:
    settings = load_settings()
    return FileKnowledgeIngestionProvider(
        flow_directory=settings.flow_directory,
        process_directory=settings.process_directory,
        processed_directory=settings.processed_directory,
        knowledge_graph_service=KnowledgeGraphService(
            Neo4jKnowledgeGraphRepository(
                settings.flow_directory,
                neo4j_uri=settings.neo4j_uri,
                neo4j_user=settings.neo4j_user,
                neo4j_password=settings.neo4j_password,
            )
        ),
    )


def build_process_execution_service() -> ProcessExecutionService:
    settings = load_settings()
    return ProcessExecutionService(
        flow_directory=settings.flow_directory,
        process_directory=settings.process_directory,
    )


def build_orchestrator_service() -> OrchestratorService:
    return OrchestratorService()


def build_ask_service() -> AskService:
    settings = load_settings()
    if not settings.use_ai_providers:
        raise RuntimeError(
            "USE_AI_PROVIDERS must be true. The ask flow requires an LLM and the Neo4j knowledge graph."
        )

    startup_records = FlowKnowledgeLoader().load_directory(settings.flow_directory)
    capability_service = CapabilityService(RegistryCapabilityProvider(startup_records))
    answer_builder = AnswerBuilder()
    approval_service = ApprovalService(AlwaysHumanApprovalPolicy())
    audit_service = AuditService(NoopAuditSink())

    try:
        return AskService(
            knowledge_graph_service=KnowledgeGraphService(
                Neo4jKnowledgeGraphRepository(
                    settings.flow_directory,
                    neo4j_uri=settings.neo4j_uri,
                    neo4j_user=settings.neo4j_user,
                    neo4j_password=settings.neo4j_password,
                )
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
            trace_directory=settings.processed_directory / "ask_trace",
        )
    except RuntimeError as exc:
        raise RuntimeError(f"Could not start required knowledge graph/LLM providers: {exc}") from exc
