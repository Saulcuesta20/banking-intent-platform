from __future__ import annotations

from app.approval.policy import AlwaysHumanApprovalPolicy
from app.approval.service import ApprovalService
from app.audit.local import NoopAuditSink
from app.audit.service import AuditService
from app.capability.local import LocalCapabilityProvider
from app.capability.service import CapabilityService
from app.config.settings import load_settings
from app.flow_context.service import FlowAnswerContextService
from app.ingestion.flow_loader import FlowKnowledgeLoader, LocalKnowledgeIngestionProvider
from app.intent.ai import LangchainReasoningProvider
from app.intent.local import LocalSemanticReasoningProvider
from app.intent.service import IntentClassificationService, IntentResolutionService
from app.query_understanding.service import (
    LLMQueryUnderstandingProvider,
    LocalQueryUnderstandingProvider,
    QueryUnderstandingService,
)
from app.retrieval.graph import GraphRAGKnowledgeRetrievalProvider
from app.retrieval.local import LocalKnowledgeRetrievalProvider
from app.retrieval.service import KnowledgeRetrievalService


def build_ingestion_provider() -> LocalKnowledgeIngestionProvider:
    settings = load_settings()
    return LocalKnowledgeIngestionProvider(
        flow_directory=settings.flow_directory,
        processed_directory=settings.processed_directory,
    )


def build_intent_service() -> IntentResolutionService:
    settings = load_settings()
    startup_records = FlowKnowledgeLoader().load_directory(settings.flow_directory)
    capability_service = CapabilityService(LocalCapabilityProvider(startup_records))
    flow_context_service = FlowAnswerContextService()
    approval_service = ApprovalService(AlwaysHumanApprovalPolicy())
    audit_service = AuditService(NoopAuditSink())

    if settings.use_ai_providers:
        try:
            return IntentResolutionService(
                retrieval_service=KnowledgeRetrievalService(
                    GraphRAGKnowledgeRetrievalProvider(
                        settings.flow_directory,
                        neo4j_uri=settings.neo4j_uri,
                        neo4j_user=settings.neo4j_user,
                        neo4j_password=settings.neo4j_password,
                        query_understanding_service=QueryUnderstandingService(
                            LLMQueryUnderstandingProvider(
                                fallback_provider=LocalQueryUnderstandingProvider(),
                                api_key=settings.openai_api_key,
                                base_url=settings.openai_base_url,
                                model=settings.intent_llm_model,
                            )
                        ),
                    )
                ),
                classification_service=IntentClassificationService(
                    LangchainReasoningProvider(
                        openai_api_key=settings.openai_api_key,
                        base_url=settings.openai_base_url,
                        model=settings.intent_llm_model,
                    )
                ),
                capability_service=capability_service,
                flow_context_service=flow_context_service,
                approval_service=approval_service,
                audit_service=audit_service,
                trace_directory=settings.processed_directory / "ask_trace",
            )
        except RuntimeError as exc:
            raise RuntimeError(f"Could not start GraphRAG LLM providers: {exc}") from exc

    return IntentResolutionService(
        retrieval_service=KnowledgeRetrievalService(
            LocalKnowledgeRetrievalProvider(settings.flow_directory)
        ),
        classification_service=IntentClassificationService(
            LocalSemanticReasoningProvider()
        ),
        capability_service=capability_service,
        flow_context_service=flow_context_service,
        approval_service=approval_service,
        audit_service=audit_service,
        trace_directory=settings.processed_directory / "ask_trace",
    )
