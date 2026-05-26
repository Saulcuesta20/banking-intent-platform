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
    participant Factory as app.factory.build_ask_service()
    participant Loader as FlowKnowledgeLoader.load_directory()
    participant IRS as AskService.resolve()
    participant LG as LangGraph StateGraph
    participant UnderstandNode as _ask_node_understand_question()
    participant SearchNode as _ask_node_search_knowledge()
    participant ClsNode as _ask_node_select_intent()
    participant ProjNode as _ask_node_build_answer()
    participant Knowledge as KnowledgeGraphService.search()
    participant Capability as CapabilityService.list_registered_actions()
    participant Classifier as FlowSelectionService.select()
    participant FlowCtx as AnswerBuilder.build()
    participant Approval as ApprovalService.enforce()
    participant Audit as AuditService.record_intent_result()
    participant Trace as AskService._write_ask_trace()
    participant Result as AnswerResult.to_dict()

    User->>CLI: ask(question)
    CLI->>Factory: build_ask_service()
    Factory->>Loader: load_directory(settings.flow_directory)
    Loader-->>Factory: startup_records
    Factory-->>CLI: AskService

    CLI->>IRS: resolve(question, trace=print_trace)
    IRS->>LG: _resolve_with_langgraph(question, trace)
    LG->>UnderstandNode: understand_question
    UnderstandNode-->>LG: question_understanding, entities
    LG->>SearchNode: search_knowledge
    SearchNode->>Knowledge: search(search_terms)
    Knowledge-->>SearchNode: list[KnowledgeRecord]
    SearchNode->>Capability: list_registered_actions()
    Capability-->>SearchNode: list[ActionRegistryEntry]
    SearchNode-->>LG: knowledge_candidates

    LG->>ClsNode: select_intent node
    ClsNode->>Classifier: select(question, records)
    Classifier-->>ClsNode: selected KnowledgeRecord or None

    alt selected_record exists
        ClsNode-->>LG: selected_record, selected_flow
        LG->>ProjNode: build_answer node
        ProjNode->>IRS: _build_projected_result(question, records, record, trace)
        IRS->>FlowCtx: build(question, record)
        FlowCtx-->>IRS: AnswerContext
        IRS->>Approval: enforce(context.plan, context.tasks)
        Approval-->>IRS: approved/gated plan and tasks
        IRS->>Approval: requires_approval()
        Approval-->>IRS: true
        IRS->>Audit: record_intent_result(question, result)
        Audit-->>IRS: recorded
        IRS->>Trace: _write_ask_trace(question, records, record, context, result)
        Trace-->>IRS: ask_trace path
        IRS-->>ProjNode: AnswerResult
        ProjNode-->>LG: result_model
    else no selected_record
        ClsNode-->>LG: selected_record=None
        LG->>IRS: _build_unknown_result(question, records, trace)
        IRS->>Approval: enforce(["clarify_customer_request"], [])
        IRS->>Audit: record_intent_result(question, unknown_result)
        IRS->>Trace: _write_ask_trace(question, records, None, None, result)
        IRS-->>LG: unknown AnswerResult
    end

    LG-->>IRS: final_state.result_model
    IRS-->>CLI: AnswerResult
    CLI->>Result: to_dict()
    Result-->>CLI: response payload
    CLI-->>User: trace summary and result
```

## Diagram 2: GraphRAG Retrieval And LLM Model Decision

This diagram zooms into the AI provider path used when `USE_AI_PROVIDERS=true`. The question is expanded for graph search, Neo4j returns candidate graph rows, LangChain formats the prompt, and the OpenAI-compatible chat completion endpoint returns the constrained JSON decision.

```mermaid
sequenceDiagram
    autonumber
    participant IRS as AskService
    participant KnowledgeSvc as KnowledgeGraphService.search()
    participant Repository as Neo4jKnowledgeGraphRepository.search()
    participant QUSvc as QuestionUnderstandingService.understand()
    participant QUProvider as LLMQuestionUnderstandingProvider.understand()
    participant QUModel as OpenAI-compatible LLM /chat/completions
    participant Neo4j as Neo4j session.run()
    participant ClassifierSvc as FlowSelectionService.select()
    participant Reasoner as LLMFlowSelectionProvider.select_intent()
    participant Prompt as LangChain PromptTemplate.format()
    participant Model as OpenAIJSONClient.complete_json()
    participant Recorder as LLMDecisionRecorder.record()
    participant FlowCtx as AnswerBuilder.build()
    participant Approval as ApprovalService
    participant Audit as AuditService

    IRS->>QUSvc: understand(question)
    QUSvc->>QUProvider: understand(question)

    QUProvider->>QUModel: POST /chat/completions(question understanding JSON prompt)
    QUModel-->>QUProvider: corrected_question, corrections, search_terms, entities, possible_intents, ambiguity
    QUProvider-->>QUSvc: QuestionUnderstanding

    QUSvc-->>IRS: QuestionUnderstanding(search_terms)
    IRS->>KnowledgeSvc: search(search_terms)
    KnowledgeSvc->>Repository: search(search_terms)
    Repository->>Neo4j: _query_graph_context(tokens)
    Neo4j-->>Repository: graph rows

    alt filtered graph rows found
        Repository-->>KnowledgeSvc: candidate KnowledgeRecord list
    else no filtered graph rows
        Repository->>Neo4j: _query_all_graph_context()
        Neo4j-->>Repository: broad graph rows
        Repository-->>KnowledgeSvc: broad-context KnowledgeRecord list
    end

    KnowledgeSvc-->>IRS: records
    IRS->>ClassifierSvc: select(question, records)
    ClassifierSvc->>Reasoner: select_intent(question, records)
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
        IRS-->>IRS: return resolved AnswerResult
    else model says unknown or invalid flow_id
        Reasoner-->>ClassifierSvc: None
        ClassifierSvc-->>IRS: None
        IRS->>Approval: enforce(["clarify_customer_request"], [])
        IRS->>Audit: record_intent_result(question, unknown_result)
        IRS-->>IRS: return unknown AnswerResult
    end
```

## Main Classes And Methods

| Step | Class / Function | Method | Responsibility |
| --- | --- | --- | --- |
| CLI entry | `app.cli` | `ask()` | Receives the question and prints trace/result. |
| Composition | `app.factory` | `build_ask_service()` | Wires LLM, GraphRAG, Neo4j, approval, audit, and answer providers into `AskService`. |
| Resolution | `AskService` | `resolve()` | Starts LangGraph ask orchestration. |
| Orchestration | `AskService` | `_resolve_with_langgraph()` | Builds and runs the ask workflow nodes. |
| Understanding node | `AskService` | `_ask_node_understand_question()` | Interprets the customer question before graph search. |
| Search node | `AskService` | `_ask_node_search_knowledge()` | Calls knowledge graph search and action registry lookup. |
| Classification node | `AskService` | `_ask_node_select_intent()` | Calls the intent classifier and stores selected flow state. |
| Projection node | `AskService` | `_ask_node_build_answer()` | Builds the resolved answer from selected answer. |
| Knowledge graph service | `KnowledgeGraphService` | `search()` | Delegates search terms to the configured repository. |
| Graph repository | `Neo4jKnowledgeGraphRepository` | `search()` | Uses search terms and Neo4j graph rows to create candidates. |
| Query understanding | `QuestionUnderstandingService` | `understand()` | Delegates query expansion to the LLM provider. |
| LLM query expansion | `LLMQuestionUnderstandingProvider` | `understand()` | Corrects typos, expands search terms, proposes possible intent hints, and detects ambiguity using an LLM. |
| Flow selection | `FlowSelectionService` | `select()` | Delegates selection to the configured reasoning provider. |
| LLM reasoning | `LLMFlowSelectionProvider` | `select_intent()` | Builds constrained prompt and selects an existing flow or unknown. |
| Model client | `OpenAIJSONClient` | `complete_json()` | Calls OpenAI-compatible `/chat/completions` and parses JSON. |
| Flow context | `AnswerBuilder` | `build()` | Projects ingested event, plan, tasks, actions, and concept. |
| Approval | `ApprovalService` | `enforce()` / `requires_approval()` | Applies human approval policy. |
| Audit | `AuditService` | `record_intent_result()` | Records the final intent event. |
| Trace | `AskService` | `_write_ask_trace()` | Writes debug trace JSON for the ask operation. |
