# Banking Intent Platform Vision And User Stories

## Purpose
Define the product vision, feature catalog, user stories, and acceptance criteria for the Banking Intent Platform.

This document is a product-facing companion to the technical specifications in `docs/specs`. It describes what the system does for users and operators, while keeping the current safety rule clear: the platform resolves, explains, plans, traces, and approval-gates banking intent, but it does not directly execute banking tools.

## Vision
The Banking Intent Platform helps a bank convert natural-language customer requests into explainable, auditable, human-approved banking workanswer.

The system should:
- Understand customer questions in natural language, including Spanish banking utterances.
- Match the request to a known, validated banking flow.
- Return the selected intent, business event, confidence, plan, user tasks,
  tools, entities currently exposed as concepts, and explanation.
- Render YAML-defined flows and user tasks in a launcher shell so that operators can browse, launch, and inspect workflows visually.
- Use graph-backed knowledge and LLM reasoning for runtime question answering.
- Fail clearly when LLM, LangGraph, or Neo4j runtime providers are unavailable.
- Keep banking execution behind human approval and external systems.
- Preserve provider boundaries so graph, LLM, retrieval, audit, approval, and ingestion implementations can be replaced.

## Personas
- Customer service agent: needs fast, explainable guidance for a customer request.
- Banking operations analyst: needs the selected flow, tasks, and back-office tools before execution.
- Knowledge engineer: maintains raw corpus material, flows, user tasks, tool registry, and graph data.
- Compliance or risk reviewer: needs approval flags, audit records, and traceability.
- Platform engineer: configures providers, CLI/API entrypoints, Neo4j, and LLM-compatible services.

## System Features

### Natural-Language Intent Resolution
The system receives a banking question and resolves it to one known flow when possible.

Current output includes:
- `can_resolve`
- `flow_id`
- `flow_name`
- `intent`
- `confidence`
- `business_event`
- `requires_human_approval`
- `plan`
- `tasks`
- `related_capabilities`
- `related_concepts`
- `explanation`

### GraphRAG Knowledge Retrieval
When AI providers are enabled, the retrieval layer queries Neo4j for graph
context across flows, utterances, entities currently stored as concepts, user
tasks, frontend tools, and backend tools.

The graph retrieval path attaches metadata such as retrieval provider, question understanding, Cypher row count, tokens, search mode, and graph row preview.

### Question Understanding
The system calls an LLM to correct obvious typos, extract search terms and entities, propose possible intent hints, and detect ambiguity before graph retrieval.

### Constrained LLM Intent Classification
The LLM reasoning provider classifies a question only against retrieved, existing knowledge records. It must select an existing flow or return `unknown`.

### Required LLM And Graph Runtime
Runtime ask requires `USE_AI_PROVIDERS=true`, an OpenAI-compatible API key, LangGraph orchestration, and Neo4j GraphRAG retrieval. If one of these providers is unavailable, the platform reports a configuration/runtime error instead of selecting an intent locally.

### Ask Answer Projection
After a flow is selected, runtime projects already-ingested knowledge into the
answer. Runtime does not create new plans, tasks, business events, tools, or
entities.

### Human Approval Gate
The approval service marks banking outcomes as requiring human approval. Sensitive banking tools remain gated and are not executed directly by AI.

### Audit And Ask Trace
The system records intent results through the audit service and writes ask traces under `data/processed/ask_trace` when configured. Trace data includes retrieval, question understanding, graph, LLM, selected flow, projected context, and final result.

### Knowledge Ingestion
The ingestion orchestrator scans raw corpus files, extracts flow/user-task/tool artifacts, validates output, writes preview or applied artifacts, and records ingestion audits.

Supported corpus inputs include text-like files, CSV, JSON, YAML, BPMN, DOCX, PDF, and common image formats. Scanned PDFs can be rendered for vision-capable LLM extraction when supporting tools are available.

### Extraction Instructions And Orchestration
The system supports optional role-based extraction instructions and LangGraph orchestration for retries, halt routing, and human-review metadata. Custom deterministic code remains responsible for validation, artifact writing, audit, and graph loading.

### Flow, User Task, And Tool Registry
Business knowledge is stored as:
- Flow nodes in Neo4j.
- Reusable UserTask nodes attached to Flow nodes.
- A derived tool registry in `graph Tool nodes/tools.registry.yaml`.

The runtime tool registry is rebuilt from current flow and user task records when the service starts.

### Neo4j Graph Loading And Inspection
Tools and CLI commands can load flow knowledge into Neo4j and inspect graph relationships for a selected flow.

### CLI Interface
The CLI supports:
- Asking a question with trace output.
- Asking without trace for raw result payloads.
- Ingesting local knowledge.
- Starting the FastAPI server.

### FastAPI Interface
The API supports:
- `POST /ask` to resolve a banking question.
- `POST /ingest` to ingest knowledge from a local source path.

### Provider Abstraction
Each major capability owns a local provider contract under its component package. `app/factory.py` composes providers but does not own component business logic.

Replaceable provider areas include retrieval, intent reasoning, question understanding, graph repository, ingestion, capability registry, approval, and audit.

## Banking Flow Coverage

| Flow ID | Flow Name | Business Event | Current Scope |
| --- | --- | --- | --- |
| `backend.operations` | Backend Operations | `BackendOperationRequested` | Coordinate customer, account, transaction, and external-system API operations. |
| `credit_note.issue` | Credit Note Issuance | `CreditNoteIssueRequested` | Identify customer, issue a credit note, and gate with business approval. |
| `customer.onboarding` | Customer Onboarding | `CustomerOnboardingRequested` | Identify customer, collect documents, screen KYC/risk, and approve onboarding. |
| `debit_note.issue` | Debit Note Issuance | `DebitNoteIssueRequested` | Identify customer, issue a debit note, and gate with business approval. |
| `fees.claims` | Fees And Claims Handling | `FeeOrClaimRequested` | Identify customer, manage a claim, and require approval. |
| `glossary.savings` | Savings Glossary Lookup | `GlossaryLookupRequested` | Explain glossary terms and banking concepts. |
| `loan.disbursement` | Loan Disbursement | `LoanDisbursementRequested` | Identify customer, review loan status, disburse funds, and require approval. |
| `loan.domain.consumer` | Consumer Loan Domain Support | `LoanDomainQuestionAsked` | Support loan-domain questions with customer, loan status, evaluation, and proposal tasks. |
| `loan.evaluation` | Loan Evaluation | `LoanEvaluationRequested` | Collect application data, evaluate eligibility, and require approval. |
| `loan.inquiry` | Loan Status Inquiry | `LoanInformationRequested` | Identify customer and review loan status. |
| `loan.payment` | Loan Payment | `LoanPaymentRequested` | Identify customer, apply loan payment, and require approval. |
| `loan.refinance` | Loan Refinance | `LoanRefinancingRequested` | Identify customer, review loan status, compare refinance options, prepare request, and require approval. |
| `loan.request` | Loan Application And Origination | `LoanRequestSubmitted` | Identify customer, collect application, evaluate, prepare proposal, and require approval. |
| `money.transfer` | Money Transfer | `MoneyTransferRequested` | Identify customer, transfer money, and require approval. |
| `savings.account.domain` | Savings Account Domain Support | `SavingsAccountDomainQuestionAsked` | Support savings-account domain questions and related operations. |
| `savings_account.open` | Savings Account Opening | `SavingsAccountOpeningRequested` | Identify customer, collect documents, KYC, create account, approve, and handle account operation. |
| `savings.operations` | Savings Account Operations | `SavingsAccountOperationRequested` | Identify customer, manage account operation or deposit, and require approval. |
| `utterance.intent.matching` | Utterance Intent Matching | `IntentMatchingRequested` | Normalize an utterance and match it to a known intent. |

## User Stories And Acceptance Criteria

### Story 1: Resolve A Customer Banking Question
As a customer service agent, I want to ask a natural-language banking question so that I can see the matching banking intent and workanswer.

Acceptance criteria:
- Given a question that matches a known flow, when the agent submits it, then the system returns `can_resolve=true`.
- Given a resolved question, when the response is returned, then it includes `flow_id`, `flow_name`, `intent`, `confidence`, `business_event`, `plan`, `tasks`, `related_capabilities`, `related_concepts`, and `explanation`.
- Given a question that does not match current flow knowledge, when the agent submits it, then the system returns `intent=unknown`, `can_resolve=false`, and an explanation.

### Story 2: Use Graph Knowledge For Candidate Retrieval
As a platform engineer, I want the system to retrieve candidate flows from Neo4j so that LLM reasoning is grounded in validated graph knowledge.

Acceptance criteria:
- Given AI providers are enabled and Neo4j is configured, when a question is submitted, then the retrieval provider queries flow, utterance, entity/concept, task, and tool graph context.
- Given matching graph rows are found, when retrieval completes, then candidate records include graph metadata and are limited by the configured retrieval limit.
- Given no filtered graph rows are found, when retrieval completes, then the system falls back to broad graph context instead of failing silently.

### Story 3: Classify Intent Against Retrieved Records
As a compliance reviewer, I want AI classification constrained to retrieved records so that it cannot invent unsupported banking flows.

Acceptance criteria:
- Given retrieved records, when LLM classification runs, then the selected flow must be one of those records or `unknown`.
- Given a selected flow, when the result is produced, then the explanation and confidence come from the selected knowledge record or constrained provider output.
- Given no matching flow, when classification runs, then the system returns the unknown-intent response path.

### Story 4: Project Ingested Flow Context
As an operations analyst, I want the selected flow to include plan, task, tool, and entity context so that I can understand the next operational steps.

Acceptance criteria:
- Given a selected `KnowledgeRecord`, when answer is built, then the system returns the record's ingested business event, plan, and tasks.
- Given user tasks contain tools, when related capabilities are projected, then those tools are included without duplicates.
- Given entities exist, when related entities are projected through the current `related_concepts` field, then nodes matching the question are prioritized before remaining nodes.

### Story 5: Require Human Approval
As a risk owner, I want sensitive banking tools to require human approval so that the platform cannot directly execute regulated tools.

Acceptance criteria:
- Given any resolved banking flow, when the final result is returned, then `requires_human_approval=true`.
- Given an unknown question, when the unknown result is returned, then approval is still required before any sensitive downstream tool.
- Given approval is enforced, when the result plan and tasks are returned, then they remain advisory workanswer and not direct execution.

### Story 6: Trace The Ask Flow
As a platform engineer, I want each ask operation to produce useful trace data so that I can debug retrieval, graph, LLM, and final response behavior.

Acceptance criteria:
- Given trace output is enabled in the CLI, when a question is submitted, then important component steps are printed.
- Given a trace directory is configured, when resolution completes, then an ask trace JSON file is written.
- Given a trace file is written, when it is inspected, then it includes retrieval metadata, question understanding, graph summary, LLM metadata, selected flow, answer, and result.

### Story 7: Require AI Providers For Ask
As a developer, I want the ask runtime to require LLM and graph providers so that every intent decision follows the same traceable AI + GraphRAG path.

Acceptance criteria:
- Given `USE_AI_PROVIDERS=false`, when the intent service is built, then it fails with a clear configuration error.
- Given no LLM API key is configured, when the CLI asks a question, then the system reports that the API key is required.
- Given Neo4j is unavailable, when retrieval runs, then the system reports the graph connection issue instead of resolving locally.

### Story 8: Ingest Raw Banking Knowledge
As a knowledge engineer, I want to ingest source documents so that flow, user task, and tool artifacts can be generated from banking corpus material.

Acceptance criteria:
- Given supported source files under a raw path, when ingestion runs, then the pipeline scans and parses those files.
- Given extracted structures are valid, when ingestion writes artifacts, then flow, user task, and tool registry outputs are created in the configured directories.
- Given ingestion completes, when the audit file is inspected, then it includes source file hashes, output identifiers, steps, timestamps, and mode.

### Story 9: Preview Or Apply Ingestion Outputs
As a knowledge engineer, I want to preview generated artifacts before applying them so that corpus extraction can be reviewed safely.

Acceptance criteria:
- Given ingestion runs in preview mode, when artifacts are written, then the result identifies preview output paths.
- Given ingestion runs in apply mode, when artifacts are written, then the configured flow, user task, and tool registry directories are updated.
- Given clean mode is enabled, when artifacts are applied, then old generated artifacts can be removed according to the pipeline configuration.

### Story 10: Use Optional Extraction Instructions
As a knowledge engineer, I want optional role-based or LangGraph-assisted ingestion so that complex corpus extraction can be reviewed and retried.

Acceptance criteria:
- Given role-based extraction instructions are enabled, when ingestion runs, then extraction instructions is included before extraction and validation.
- Given LangGraph orchestration is enabled, when extraction validation fails, then the workflow can route through retry or failure branches.

### Story 11: Maintain The Tool Registry
As an operations analyst, I want tools linked to user tasks and flows so that the operational capabilities behind a customer intent are visible.

Acceptance criteria:
- Given flow and user task records exist, when the service starts, then the tool registry can be rebuilt from current artifacts.
- Given a selected flow has user tasks, when the response is produced, then tools appear in `related_capabilities`.
- Given the tool registry is inspected, when an tool is selected, then it lists related user tasks and flows.

### Story 12: Load And Inspect The Graph
As a platform engineer, I want to load generated flow knowledge into Neo4j and inspect graph neighbors so that I can validate the knowledge graph.

Acceptance criteria:
- Given Neo4j is running, when `kb reset-ingest --raw data/raw/enterprise_dump_2026` is executed, then flow knowledge is persisted as graph nodes and relationships.
- Given a flow ID and depth, when `kb query --id <flow_id> --tree` is executed, then related graph entities are displayed.
- Given graph loading fails, when the command exits, then the error should be visible to the operator.

### Story 13: Use The CLI
As a developer or analyst, I want CLI commands so that I can operate the platform locally.

Acceptance criteria:
- Given a question, when `ask` or `python -m app.cli ask` is executed, then the system returns trace and summary output by default.
- Given `--no-trace` or full-result options are used, when the ask command runs, then the output shape follows the requested mode.
- Given a source path, when the ingest command runs, then it returns status, source, record count, and ingested intents.

### Story 14: Use The API
As an integration developer, I want an HTTP API so that other systems can call intent resolution and ingestion.

Acceptance criteria:
- Given the server is running, when `POST /ask` receives `{"question": "..."}`, then it returns the intent result payload.
- Given the server is running, when `POST /ingest` receives `{"source_path": "..."}`, then it returns ingestion status and ingested intents.
- Given an internal provider error occurs, when the API handles the request, then it returns an HTTP 500 with error detail.

### Story 15: Preserve Provider Replaceability
As a platform architect, I want component-local provider interfaces so that implementation frameworks can be replaced without changing business services.

Acceptance criteria:
- Given a new graph, retrieval, LLM, audit, approval, or ingestion provider is introduced, when it implements the component-local interface, then the composition root can wire it.
- Given provider implementations change, when domain services are inspected, then they remain independent from framework-specific types.
- Given `app/factory.py` changes provider selection, when the application starts, then existing CLI and API contracts remain stable.

### Story 16: Support Savings And Loan Domain Flows
As a banking tools team, I want savings, loan, payment, transfer, note, claim, onboarding, and glossary flows so that common customer intents can be routed consistently.

Acceptance criteria:
- Given utterances for loan refinance, loan request, loan payment, loan inquiry, loan evaluation, or loan disbursement, when questions are submitted, then the system resolves to the matching loan flow where knowledge exists.
- Given utterances for savings account opening, savings operations, savings glossary, or savings domain support, when questions are submitted, then the system resolves to the matching savings flow where knowledge exists.
- Given utterances for money transfer, credit note, debit note, fees/claims, customer onboarding, backend operations, or intent matching, when questions are submitted, then the system resolves to the matching operational flow where knowledge exists.

### Story 17: Browse And Launch YAML-Defined Flows In The Launcher
As an operations analyst, I want to browse flow definitions in the launcher so that I can inspect and start approved workflows without opening raw YAML files.

Acceptance criteria:
- Given a flow definition exists under `config/definitions/flows`, when the launcher opens the flow browser, then the flow is rendered as cards, steps, or a stepper view driven from the YAML source.
- Given a flow has attached `user_task` definitions, when the user opens the flow detail, then the launcher shows the associated user actions, required inputs, and related tools.
- Given a flow is selected, when the user launches it, then the launcher opens the chat/workspace and logs with the selected flow context already loaded.

### Story 18: Inspect Logs And Context While A Flow Runs
As a platform engineer, I want to see live logs and context in the launcher so that I can understand what the system is doing during workflow execution.

Acceptance criteria:
- Given a workflow is running, when the launcher opens the log panel, then it shows the current run status, timestamps, and recent events.
- Given a selected flow or process, when the user opens the context panel, then it shows the current asset, metadata, rulesets, and related assets.
- Given a workflow finishes or fails, when the result arrives, then the launcher updates the workspace and trace view without losing the selected context.

## Non-Functional Requirements
- Explainability: every resolved answer must expose the selected intent, business event, plan, tasks, capabilities, entities, and explanation. Current API field names still expose entities as concepts.
- Auditability: ask and ingestion flows must be traceable through audit or trace records.
- Safety: AI may classify and explain, but must not directly execute banking tools.
- Configurability: AI and graph providers must be replaceable through provider interfaces.
- Runtime consistency: ask must always use the LLM + GraphRAG + Neo4j path or fail clearly.
- Data quality: ingestion must validate generated JSON artifacts before they become runtime knowledge.
- Separation of concerns: runtime question answering must project ingested knowledge rather than generating new operational plans.

## Out Of Scope For Current MVP
- Direct execution of money movement, account creation, loan disbursement, or note issuance.
- Full authentication and authorization model for production API access.
- Persistent production audit sink beyond the current provider abstrtool.
- End-user UI.
- Real-time core banking integration.
- Dynamic runtime creation of new flows, tasks, events, or entities during question answering.

## Success Metrics
- Known-flow questions resolve to the correct `flow_id` with meaningful confidence.
- Unknown questions return a safe unknown response with approval required.
- Ask traces provide enough context to debug retrieval and classification decisions.
- Ingestion produces valid flow, user task, and tool artifacts from supported corpus files.
- Provider replacement does not require changes to CLI/API contracts or domain models.
