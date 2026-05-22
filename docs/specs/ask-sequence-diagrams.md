# Ask Sequence Diagrams

## Purpose
Show which classes and methods are invoked from the moment a user runs `ask` until the platform returns an intent result.

The diagrams use Mermaid sequence syntax so they can be rendered by GitHub and most Markdown tools.

## Diagram 1: CLI `ask` To Final Intent Result

This diagram shows the main successful path when `python -m app.cli ask "..."` or `make ask` is used. The service runs LangGraph ask orchestration, and the graph nodes call retrieval, classification, projection, approval, audit, and trace-writing methods.

```mermaid
sequenceDiagram
    autonumber
    actor User as User / Agent
    participant CLI as app.cli.ask()
    participant Factory as app.factory.build_intent_service()
    participant Loader as FlowKnowledgeLoader.load_directory()
    participant IRS as IntentResolutionService.resolve()
    participant LG as LangGraph StateGraph
    participant RetNode as _ask_node_retrieve_context()
    participant ClsNode as _ask_node_classify_intent()
    participant ProjNode as _ask_node_project_flow_context()
    participant Retrieval as KnowledgeRetrievalService.retrieve()
    participant Capability as CapabilityService.list_registered_actions()
    participant Classifier as IntentClassificationService.classify()
    participant FlowCtx as FlowAnswerContextService.build()
    participant Approval as ApprovalService.enforce()
    participant Audit as AuditService.record_intent_result()
    participant Trace as IntentResolutionService._write_ask_trace()
    participant Result as IntentResult.to_dict()

    User->>CLI: ask(question)
    CLI->>Factory: build_intent_service()
    Factory->>Loader: load_directory(settings.flow_directory)
    Loader-->>Factory: startup_records
    Factory-->>CLI: IntentResolutionService

    CLI->>IRS: resolve(question, trace=print_trace)
    IRS->>LG: _resolve_with_langgraph(question, trace)
    LG->>RetNode: invoke({question, trace})
    RetNode->>Retrieval: retrieve(question)
    Retrieval-->>RetNode: list[KnowledgeRecord]
    RetNode->>Capability: list_registered_actions()
    Capability-->>RetNode: list[ActionRegistryEntry]
    RetNode-->>LG: retrieved_context, entities

    LG->>ClsNode: classify_intent node
    ClsNode->>Classifier: classify(question, records)
    Classifier-->>ClsNode: selected KnowledgeRecord or None

    alt selected_record exists
        ClsNode-->>LG: selected_record, selected_flow
        LG->>ProjNode: project_flow_context node
        ProjNode->>IRS: _build_projected_result(question, records, record, trace)
        IRS->>FlowCtx: build(question, record)
        FlowCtx-->>IRS: FlowAnswerContext
        IRS->>Approval: enforce(context.plan, context.tasks)
        Approval-->>IRS: approved/gated plan and tasks
        IRS->>Approval: requires_approval()
        Approval-->>IRS: true
        IRS->>Audit: record_intent_result(question, result)
        Audit-->>IRS: recorded
        IRS->>Trace: _write_ask_trace(question, records, record, context, result)
        Trace-->>IRS: ask_trace path
        IRS-->>ProjNode: IntentResult
        ProjNode-->>LG: result_model
    else no selected_record
        ClsNode-->>LG: selected_record=None
        LG->>IRS: _build_unknown_result(question, records, trace)
        IRS->>Approval: enforce(["clarify_customer_request"], [])
        IRS->>Audit: record_intent_result(question, unknown_result)
        IRS->>Trace: _write_ask_trace(question, records, None, None, result)
        IRS-->>LG: unknown IntentResult
    end

    LG-->>IRS: final_state.result_model
    IRS-->>CLI: IntentResult
    CLI->>Result: to_dict()
    Result-->>CLI: response payload
    CLI-->>User: trace summary and result
```

## Diagram 2: GraphRAG Retrieval And LLM Model Decision

This diagram zooms into the AI provider path used when `USE_AI_PROVIDERS=true`. The question is expanded for graph search, Neo4j returns candidate graph rows, LangChain formats the prompt, and the OpenAI-compatible chat completion endpoint returns the constrained JSON decision.

```mermaid
sequenceDiagram
    autonumber
    participant IRS as IntentResolutionService
    participant RetrievalSvc as KnowledgeRetrievalService.retrieve()
    participant GraphRAG as GraphRAGKnowledgeRetrievalProvider.retrieve()
    participant QUSvc as QueryUnderstandingService.understand()
    participant QUProvider as LLMQueryUnderstandingProvider.understand()
    participant QUModel as OpenAI-compatible LLM /chat/completions
    participant Neo4j as Neo4j session.run()
    participant ClassifierSvc as IntentClassificationService.classify()
    participant Reasoner as LangchainGraphRAGReasoningProvider.classify_intent()
    participant Prompt as LangChain PromptTemplate.format()
    participant Model as OpenAIJSONClient.complete_json()
    participant Recorder as LLMDecisionRecorder.record()
    participant FlowCtx as FlowAnswerContextService.build()
    participant Approval as ApprovalService
    participant Audit as AuditService

    IRS->>RetrievalSvc: retrieve(question)
    RetrievalSvc->>GraphRAG: retrieve(question)
    GraphRAG->>QUSvc: understand(question)
    QUSvc->>QUProvider: understand(question)

    QUProvider->>QUModel: POST /chat/completions(query understanding JSON prompt)
    QUModel-->>QUProvider: corrected_question, corrections, search_terms, entities, possible_intents, ambiguity
    QUProvider-->>QUSvc: LLM QueryUnderstanding

    QUSvc-->>GraphRAG: QueryUnderstanding(search_terms)
    GraphRAG->>Neo4j: _query_graph_context(tokens)
    Neo4j-->>GraphRAG: graph rows

    alt filtered graph rows found
        GraphRAG->>GraphRAG: attach graph_context and metadata to records
        GraphRAG-->>RetrievalSvc: candidate KnowledgeRecord list
    else no filtered graph rows
        GraphRAG->>Neo4j: _query_all_graph_context()
        Neo4j-->>GraphRAG: broad graph rows
        GraphRAG-->>RetrievalSvc: broad-context KnowledgeRecord list
    end

    RetrievalSvc-->>IRS: records
    IRS->>ClassifierSvc: classify(question, records)
    ClassifierSvc->>Reasoner: classify_intent(question, records)
    Reasoner->>Prompt: format(question, query_understanding, graph_context)
    Prompt-->>Reasoner: constrained prompt
    Reasoner->>Model: complete_json(prompt)
    Model->>Model: POST /chat/completions(response_format=json_object)
    Model-->>Reasoner: can_resolve, selected_flow_id, confidence, reason
    Reasoner->>Recorder: record(prompt, answer)

    alt model selected valid flow_id
        Reasoner-->>ClassifierSvc: KnowledgeRecord with LLM metadata
        ClassifierSvc-->>IRS: selected KnowledgeRecord
        IRS->>FlowCtx: build(question, record)
        IRS->>Approval: enforce(plan, tasks)
        IRS->>Audit: record_intent_result(question, result)
        IRS-->>IRS: return resolved IntentResult
    else model says unknown or invalid flow_id
        Reasoner-->>ClassifierSvc: None
        ClassifierSvc-->>IRS: None
        IRS->>Approval: enforce(["clarify_customer_request"], [])
        IRS->>Audit: record_intent_result(question, unknown_result)
        IRS-->>IRS: return unknown IntentResult
    end
```

## Main Classes And Methods

| Step | Class / Function | Method | Responsibility |
| --- | --- | --- | --- |
| CLI entry | `app.cli` | `ask()` | Receives the question and prints trace/result. |
| Composition | `app.factory` | `build_intent_service()` | Wires LLM, GraphRAG, Neo4j, approval, audit, and flow context providers into `IntentResolutionService`. |
| Resolution | `IntentResolutionService` | `resolve()` | Starts LangGraph ask orchestration. |
| Orchestration | `IntentResolutionService` | `_resolve_with_langgraph()` | Builds and runs the ask workflow nodes. |
| Retrieval node | `IntentResolutionService` | `_ask_node_retrieve_context()` | Calls retrieval and action registry lookup. |
| Classification node | `IntentResolutionService` | `_ask_node_classify_intent()` | Calls the intent classifier and stores selected flow state. |
| Projection node | `IntentResolutionService` | `_ask_node_project_flow_context()` | Builds the resolved answer from selected flow context. |
| Retrieval service | `KnowledgeRetrievalService` | `retrieve()` | Delegates retrieval to the configured provider. |
| Graph retrieval | `GraphRAGKnowledgeRetrievalProvider` | `retrieve()` | Uses query understanding and Neo4j graph rows to create candidates. |
| Query understanding | `QueryUnderstandingService` | `understand()` | Delegates query expansion to the LLM provider. |
| LLM query expansion | `LLMQueryUnderstandingProvider` | `understand()` | Corrects typos, expands search terms, proposes possible intent hints, and detects ambiguity using an LLM. |
| Intent classifier | `IntentClassificationService` | `classify()` | Delegates classification to the configured reasoning provider. |
| LLM reasoning | `LangchainGraphRAGReasoningProvider` | `classify_intent()` | Builds constrained prompt and selects an existing flow or unknown. |
| Model client | `OpenAIJSONClient` | `complete_json()` | Calls OpenAI-compatible `/chat/completions` and parses JSON. |
| Flow context | `FlowAnswerContextService` | `build()` | Projects ingested event, plan, tasks, actions, and ontology. |
| Approval | `ApprovalService` | `enforce()` / `requires_approval()` | Applies human approval policy. |
| Audit | `AuditService` | `record_intent_result()` | Records the final intent event. |
| Trace | `IntentResolutionService` | `_write_ask_trace()` | Writes debug trace JSON for the ask operation. |
